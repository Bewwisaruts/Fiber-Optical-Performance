"""
seed_owner.py
=============
สร้างบัญชี Owner คนแรกเข้าฐานข้อมูล — ต้องรันสคริปต์นี้ "ครั้งเดียว" ตอน setup ระบบใหม่
(รันจากเครื่อง ไม่ใช่ผ่าน API เพราะ API สร้าง user ต้อง login เป็น owner ก่อน แต่ตอนนี้ยังไม่มี owner เลย)

วิธีใช้:
    python seed_owner.py
    (จะถามชื่อผู้ใช้ + รหัสผ่านแบบ interactive)

หรือระบุตรงๆ ผ่าน argument:
    python seed_owner.py --username admin_owner --password "รหัสผ่านยาวๆ"

ถ้ามี owner อยู่แล้วในระบบ สคริปต์จะเตือนแล้วถามยืนยันก่อนสร้างซ้ำ/แทนที่
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auth import hash_password  # noqa: E402

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


def _env(key, default=None):
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    return val.strip()


def get_engine():
    db_user = _env("DB_USER", "postgres")
    db_password = _env("DB_PASSWORD")
    db_host = _env("DB_HOST")
    db_port = _env("DB_PORT", "5432")
    db_name = _env("DB_NAME", "postgres")
    db_sslmode = _env("DB_SSLMODE", "require")

    if not db_password or not db_host:
        print(f"[error] ไม่พบ DB_PASSWORD หรือ DB_HOST ใน {ENV_PATH}")
        sys.exit(1)

    url = URL.create(
        drivername="postgresql",
        username=db_user, password=db_password, host=db_host,
        port=int(db_port), database=db_name, query={"sslmode": db_sslmode},
    )
    return create_engine(url)


def main():
    parser = argparse.ArgumentParser(description="สร้างบัญชี Owner คนแรก")
    parser.add_argument("--username", help="ชื่อผู้ใช้ของ Owner")
    parser.add_argument("--password", help="รหัสผ่าน (ถ้าไม่ระบุจะถามแบบซ่อนตัวอักษร)")
    args = parser.parse_args()

    engine = get_engine()

    with engine.begin() as conn:
        existing_owner = conn.execute(
            text("SELECT username FROM users WHERE role = 'owner' LIMIT 1")
        ).fetchone()

        if existing_owner:
            print(f"[warning] มี Owner อยู่แล้วในระบบ: '{existing_owner[0]}'")
            confirm = input("ต้องการยกเลิก Owner คนเดิมแล้วตั้งคนใหม่แทนหรือไม่? (พิมพ์ yes เพื่อยืนยัน): ")
            if confirm.strip().lower() != "yes":
                print("ยกเลิกการทำงาน")
                return
            conn.execute(text("UPDATE users SET role = 'admin' WHERE role = 'owner'"))
            print(f"[ok] ลด role ของ '{existing_owner[0]}' เป็น admin แล้ว")

        username = args.username or input("ตั้งชื่อผู้ใช้สำหรับ Owner: ").strip()
        if not username:
            print("[error] ต้องระบุชื่อผู้ใช้")
            sys.exit(1)

        password = args.password or getpass.getpass("ตั้งรหัสผ่านสำหรับ Owner (พิมพ์ไม่โชว์ตัวอักษร): ")
        if len(password) < 8:
            print("[error] รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร")
            sys.exit(1)

        password_hash = hash_password(password)

        existing_user = conn.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": username}
        ).fetchone()

        if existing_user:
            conn.execute(
                text("UPDATE users SET password_hash = :ph, role = 'owner', updated_at = now() WHERE username = :u"),
                {"ph": password_hash, "u": username},
            )
            print(f"[ok] อัปเดตผู้ใช้ '{username}' ที่มีอยู่แล้วให้เป็น Owner และตั้งรหัสผ่านใหม่เรียบร้อย")
        else:
            conn.execute(
                text("INSERT INTO users (username, password_hash, role) VALUES (:u, :ph, 'owner')"),
                {"u": username, "ph": password_hash},
            )
            print(f"[ok] สร้างบัญชี Owner '{username}' สำเร็จเรียบร้อย")

    print("\nตอนนี้ล็อกอินผ่านหน้า Login.html ด้วยบัญชีนี้ได้เลย")


if __name__ == "__main__":
    main()