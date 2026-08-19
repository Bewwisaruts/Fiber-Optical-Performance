import os
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import create_engine, text

# ==========================================
# 1. Config (แยกจาก fast.py เพื่อไม่ต้องไปแก้ engine เดิม)
#    ค่า default คัดลอกมาจาก fast.py — ปรับให้ตรงกับของจริง หรือย้ายไปใช้ .env ทีหลังได้
# ==========================================
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "bew30012548")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "Client-Card")

SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "CHANGE_THIS_TO_A_RANDOM_LONG_STRING_BEFORE_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", "480"))  # 8 ชม.

auth_engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

router = APIRouter(tags=["auth"])


# ==========================================
# 2. สร้างตาราง app_users อัตโนมัติถ้ายังไม่มี (ไม่แตะตารางเดิมของโปรเจกต์)
# ==========================================
def ensure_users_table():
    with auth_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(64) UNIQUE NOT NULL,
                full_name VARCHAR(128),
                hashed_password TEXT NOT NULL,
                role VARCHAR(32) NOT NULL DEFAULT 'viewer',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT now()
            );
        """))

ensure_users_table()


# ==========================================
# 3. Password helpers (ใช้ bcrypt โดยตรง ไม่พึ่ง passlib)
#    bcrypt จำกัด input ไว้ที่ 72 bytes โดยธรรมชาติ ตัดให้ปลอดภัยก่อน encode
# ==========================================
def hash_password(plain_password: str) -> str:
    pw_bytes = plain_password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        return False


# ==========================================
# 4. DB helpers เฉพาะเรื่อง user (ไม่ยุ่งกับตารางอื่น)
# ==========================================
def get_user(username: str):
    with auth_engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM app_users WHERE username = :u"), {"u": username}
        ).mappings().first()
        return dict(row) if row else None

def create_user(username: str, password: str, full_name: str = "", role: str = "viewer"):
    with auth_engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO app_users (username, full_name, hashed_password, role)
            VALUES (:u, :f, :p, :r)
            ON CONFLICT (username) DO NOTHING;
        """), {"u": username, "f": full_name, "p": hash_password(password), "r": role})


# ==========================================
# 5. JWT helpers
# ==========================================
def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    """ ใช้เป็น Depends() แปะกับ endpoint ที่ต้องการให้ login ก่อนถึงเข้าถึงได้ """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ไม่สามารถยืนยันตัวตนได้ กรุณา login ใหม่",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user(username)
    if user is None or not user["is_active"]:
        raise credentials_exception
    return user


def require_role(*allowed_roles: str):
    """ ตัวอย่างการจำกัด role เช่น require_role('admin') สำหรับ endpoint ที่ให้เฉพาะ admin """
    def _checker(user=Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงส่วนนี้")
        return user
    return _checker


# ==========================================
# 6. Endpoint: /api/login
# ==========================================
@router.post("/api/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="บัญชีนี้ถูกระงับการใช้งาน")

    access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
        "role": user["role"],
    }


@router.get("/api/me")
def read_me(current_user=Depends(get_current_user)):
    return {
        "status": "success",
        "username": current_user["username"],
        "full_name": current_user["full_name"],
        "role": current_user["role"],
    }

# ==========================================
# 7. Endpoints สำหรับจัดการผู้ใช้งาน (Users Management)
# ==========================================

@router.get("/api/users")
def get_all_users(current_user=Depends(require_role("owner"))):
    """ดึงรายชื่อผู้ใช้ทั้งหมด (ให้เฉพาะ owner เข้าถึงได้)"""
    with auth_engine.connect() as conn:
        # ไม่ดึง hashed_password ออกมาเพื่อความปลอดภัย
        rows = conn.execute(text("""
            SELECT id, username, full_name, role, is_active, created_at 
            FROM app_users 
            ORDER BY created_at ASC
        """)).mappings().all()
        
        return {"status": "success", "users": [dict(row) for row in rows]}


@router.post("/api/users")
def api_create_user(req: UserCreateRequest , current_user=Depends(require_role("owner"))):
    """สร้างผู้ใช้ใหม่"""
    # 1. ยืนยันรหัสผ่านของ owner ก่อน
    if not verify_password(req.confirm_password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="รหัสผ่านยืนยันตัวตน (Owner) ไม่ถูกต้อง")
    
    # 2. ตรวจสอบ username ซ้ำ
    if get_user(req.username):
        raise HTTPException(status_code=400, detail=f"Username '{req.username}' มีอยู่แล้วในระบบ")
    
    # 3. บันทึกลงฐานข้อมูล
    create_user(username=req.username, password=req.password, full_name=req.full_name, role=req.role)
    return {"status": "success", "message": f"สร้างผู้ใช้ '{req.username}' สำเร็จ"}


@router.patch("/api/users/{target_username}")
def api_update_user(target_username: str, req: UserUpdateRequest , current_user=Depends(require_role("owner"))):
    """แก้ไข Role, Password หรือ สถานะ ของผู้ใช้งาน"""
    target_user = get_user(target_username)
    if not target_user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้งานนี้ในระบบ")
    
    if target_user["role"] == "owner":
        raise HTTPException(status_code=400, detail="ไม่สามารถแก้ไขข้อมูลบัญชี Owner ด้วยวิธีนี้ได้")

    updates = []
    params = {"u": target_username}

    if req.role is not None:
        if req.role not in ["admin", "viewer"]:
            raise HTTPException(status_code=400, detail="Role ต้องเป็น admin หรือ viewer เท่านั้น")
        updates.append("role = :r")
        params["r"] = req.role

    if req.password is not None:
        updates.append("hashed_password = :p")
        params["p"] = hash_password(req.password)

    if req.is_active is not None:
        updates.append("is_active = :a")
        params["a"] = req.is_active

    if updates:
        query = f"UPDATE app_users SET {', '.join(updates)} WHERE username = :u"
        with auth_engine.begin() as conn:
            conn.execute(text(query), params)

    return {"status": "success", "message": "อัปเดตข้อมูลสำเร็จ"}


@router.delete("/api/users/{target_username}")
def api_delete_user(target_username: str, req: UserDeleteRequest, current_user=Depends(require_role("owner"))):
    """ลบผู้ใช้งาน"""
    if not verify_password(req.confirm_password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="รหัสผ่านยืนยันตัวตน (Owner) ไม่ถูกต้อง")

    target_user = get_user(target_username)
    if not target_user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้งานนี้ในระบบ")
    
    if target_user["role"] == "owner":
        raise HTTPException(status_code=400, detail="ไม่สามารถลบบัญชี Owner ได้ ต้องโอนสิทธิ์ให้ผู้อื่นก่อน")

    with auth_engine.begin() as conn:
        conn.execute(text("DELETE FROM app_users WHERE username = :u"), {"u": target_username})
        
    return {"status": "success", "message": f"ลบผู้ใช้ '{target_username}' สำเร็จ"}


@router.post("/api/users/transfer-ownership")
def api_transfer_ownership(req: TransferOwnershipRequest, current_user=Depends(require_role("owner"))):
    """โอนสิทธิ์ Owner ให้ผู้ใช้อื่น"""
    if not verify_password(req.confirm_password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="รหัสผ่านยืนยันตัวตน (Owner) ไม่ถูกต้อง")

    target_user = get_user(req.target_username)
    if not target_user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้งานปลายทางในระบบ")
    
    if target_user["role"] == "owner":
        raise HTTPException(status_code=400, detail="ผู้ใช้งานนี้เป็น Owner อยู่แล้ว")

    with auth_engine.begin() as conn:
        # ลดสิทธิ์ Owner ปัจจุบันให้กลายเป็น admin
        conn.execute(
            text("UPDATE app_users SET role = 'admin' WHERE username = :u"), 
            {"u": current_user["username"]}
        )
        # เลื่อนขั้นเป้าหมายให้เป็น owner
        conn.execute(
            text("UPDATE app_users SET role = 'owner' WHERE username = :u"), 
            {"u": req.target_username}
        )

    return {"status": "success", "message": f"โอนสิทธิ์ Owner ให้ '{req.target_username}' สำเร็จ"}
