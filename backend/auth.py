"""
auth.py
=======
โมดูลรวมทุกอย่างเกี่ยวกับ authentication / authorization:
- hash / verify รหัสผ่านด้วย bcrypt
- ออกและตรวจ JWT access token
- FastAPI Dependency สำหรับเช็คว่า login แล้วหรือยัง (get_current_user)
- FastAPI Dependency สำหรับเช็ค role (require_roles)

ต้องมีตัวแปร JWT_SECRET ใน .env (ดู .env.example) — เป็นกุญแจเซ็นต์ token
ห้ามให้ค่านี้หลุด ถ้าหลุดคนอื่นจะปลอมโทเคนเป็นใครก็ได้
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# โหลด .env จากโฟลเดอร์เดียวกับไฟล์นี้ (เผื่อถูก import จากที่อื่น)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480") or "480")  # ค่าเริ่มต้น 8 ชั่วโมง

if not JWT_SECRET:
    raise RuntimeError(
        "ไม่พบ JWT_SECRET ใน .env — เพิ่มบรรทัด JWT_SECRET=<สุ่มตัวอักษรยาวๆ อย่างน้อย 32 ตัว> "
        "ก่อนรัน (สุ่มได้ด้วยคำสั่ง: python -c \"import secrets; print(secrets.token_hex(32))\")"
    )

security = HTTPBearer(auto_error=True)

ROLES = ("owner", "admin", "visitor")


# ---------- Password hashing ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------- JWT ----------

def create_access_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="โทเคนไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่")


# ---------- FastAPI Dependencies ----------

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """ ใช้เป็น Depends() ในทุก endpoint ที่ต้อง login ก่อนถึงจะเรียกได้ """
    payload = decode_access_token(credentials.credentials)
    return {
        "id": int(payload["sub"]),
        "username": payload["username"],
        "role": payload["role"],
    }


def require_roles(*allowed_roles: str):
    """
    ใช้เป็น Depends(require_roles("owner")) หรือ Depends(require_roles("owner","admin"))
    ใน endpoint ที่ต้องจำกัดสิทธิ์เฉพาะ role ที่ระบุ
    """
    allowed = set(allowed_roles)

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"การกระทำนี้ต้องมีสิทธิ์ {' หรือ '.join(sorted(allowed))} เท่านั้น "
                       f"(บัญชีของคุณมีสิทธิ์ระดับ {user['role']})",
            )
        return user

    return checker