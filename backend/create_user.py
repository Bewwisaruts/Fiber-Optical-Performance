import getpass
from sqlalchemy import text
from auth import auth_engine, get_user, create_user, verify_password

# Role ที่สามารถกำหนดทั่วไปได้ ( owner จะถูกจัดการพิเศษแยกต่างหาก )
ASSIGNABLE_ROLES = {"admin", "viewer"}


def get_owner_user():
    """ค้นหาผู้ใช้ที่เป็น owner ในระบบ (มีได้สูงสุดเพียง 1 คน)"""
    with auth_engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM app_users WHERE role = 'owner' LIMIT 1")
        ).mappings().first()
        return dict(row) if row else None


def update_user_role(username: str, new_role: str):
    """อัปเดต role ของผู้ใช้ในฐานข้อมูล"""
    with auth_engine.begin() as conn:
        conn.execute(
            text("UPDATE app_users SET role = :r WHERE username = :u"),
            {"r": new_role, "u": username}
        )


def delete_user_by_username(username: str):
    """ลบผู้ใช้งานออกจากฐานข้อมูล"""
    with auth_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM app_users WHERE username = :u"),
            {"u": username}
        )


def confirm_owner_password(owner_user: dict) -> bool:
    """ยืนยันตัวตนด้วยรหัสผ่านของ Owner"""
    print(f"\n🔒 การดำเนินการนี้ต้องได้รับการยืนยันจาก Owner ('{owner_user['username']}')")
    password = getpass.getpass(f"กรุณากรอกรหัสผ่านของ Owner ({owner_user['username']}): ")
    if not verify_password(password, owner_user["hashed_password"]):
        print("❌ รหัสผ่าน Owner ไม่ถูกต้อง! ยกเลิกการทำงาน")
        return False
    return True


def handle_create_user():
    print("\n--- [1] เพิ่มผู้ใช้งานใหม่ ---")
    existing_owner = get_owner_user()

    # หากมี Owner ในระบบแล้ว ต้องยืนยันรหัสผ่าน Owner ก่อนสร้าง User ใหม่
    if existing_owner:
        if not confirm_owner_password(existing_owner):
            return

    username = input("Username: ").strip()
    if not username:
        print("❌ Username ห้ามเป็นค่าว่าง")
        return

    if get_user(username):
        print(f"❌ Username '{username}' มีอยู่แล้วในระบบ")
        return

    password = getpass.getpass("Password: ")
    password_confirm = getpass.getpass("Confirm Password: ")
    if password != password_confirm:
        print("❌ รหัสผ่านไม่ตรงกัน")
        return

    full_name = input("Full name (ไม่บังคับ): ").strip()

    if existing_owner:
        # มี Owner อยู่แล้ว -> เลือกสร้างได้แค่ admin หรือ viewer
        role = input(f"Role [{'/'.join(sorted(ASSIGNABLE_ROLES))}] (default: viewer): ").strip() or "viewer"
        if role not in ASSIGNABLE_ROLES:
            print(f"❌ ระบบมี Owner แล้ว สร้างได้เฉพาะ Role: {sorted(ASSIGNABLE_ROLES)}")
            return
    else:
        # ยังไม่มี Owner (การ Bootstrap ระบบครั้งแรก)
        role = input("Role [owner/admin/viewer] (default: owner): ").strip() or "owner"
        if role not in ({"owner"} | ASSIGNABLE_ROLES):
            print(f"❌ Role ต้องเป็นหนึ่งใน {sorted({'owner'} | ASSIGNABLE_ROLES)}")
            return

    create_user(username=username, password=password, full_name=full_name, role=role)
    print(f"✅ สร้างผู้ใช้ '{username}' (role: {role}) สำเร็จ")


def handle_transfer_owner():
    print("\n--- [2] โอนสิทธิ์ Owner ---")
    existing_owner = get_owner_user()
    if not existing_owner:
        print("❌ ยังไม่มี Owner ในระบบ ไม่สามารถทำการโอนสิทธิ์ได้")
        return

    target_username = input("กรอก Username ของผู้ใช้ที่ต้องการโอนสิทธิ์ Owner ให้: ").strip()
    if target_username == existing_owner["username"]:
        print("❌ ผู้ใช้งานนี้เป็น Owner อยู่แล้ว")
        return

    target_user = get_user(target_username)
    if not target_user:
        print(f"❌ ไม่พบผู้ใช้ '{target_username}' ในระบบ")
        return

    # ยืนยันรหัสผ่านของ Owner เดิม
    if not confirm_owner_password(existing_owner):
        return

    old_owner_new_role = input(f"ระบุ Role ใหม่ของ Owner เดิม ({existing_owner['username']}) [admin/viewer] (default: admin): ").strip() or "admin"
    if old_owner_new_role not in ASSIGNABLE_ROLES:
        print(f"❌ Role ใหม่ต้องเป็น {sorted(ASSIGNABLE_ROLES)}")
        return

    # ปรับสิทธิ์ Owner เดิมเป็น Role ใหม่ และปรับผู้ใช้เป้าหมายเป็น Owner
    update_user_role(existing_owner["username"], old_owner_new_role)
    update_user_role(target_username, "owner")
    
    print(f"✅ โอนสิทธิ์ Owner ให้กับ '{target_username}' เรียบร้อยแล้ว")
    print(f"   -> '{existing_owner['username']}' ถูกปรับ Role เป็น '{old_owner_new_role}'")


def handle_delete_user():
    print("\n--- [3] ลบผู้ใช้งาน ---")
    existing_owner = get_owner_user()
    if existing_owner:
        if not confirm_owner_password(existing_owner):
            return
    else:
        print("❌ ไม่พบ Owner ในระบบ ไม่สามารถทำการลบผู้ใช้งานได้")
        return

    target_username = input("กรอก Username ที่ต้องการลบ: ").strip()
    if target_username == existing_owner["username"]:
        print("❌ ไม่สามารถลบ Owner ปัจจุบันได้ (ต้องโอนสิทธิ์ Owner ให้ผู้อื่นก่อน)")
        return

    target_user = get_user(target_username)
    if not target_user:
        print(f"❌ ไม่พบผู้ใช้ '{target_username}' ในระบบ")
        return

    confirm_del = input(f"⚠️ คุณแน่ใจหรือไม่ที่จะลบผู้ใช้ '{target_username}' ? (y/N): ").strip().lower()
    if confirm_del == "y":
        delete_user_by_username(target_username)
        print(f"✅ ลบผู้ใช้ '{target_username}' ออกจากระบบเรียบร้อยแล้ว")
    else:
        print("ยกเลิกการลบผู้ใช้งาน")


def main():
    print("=== ระบบจัดการผู้ใช้งาน (CLI User Management) ===")
    print("1. เพิ่มผู้ใช้งาน (Add User)")
    print("2. โอนสิทธิ์ Owner (Transfer Owner)")
    print("3. ลบผู้ใช้งาน (Delete User)")
    
    choice = input("เลือกเมนู (1-3): ").strip()
    if choice == "1":
        handle_create_user()
    elif choice == "2":
        handle_transfer_owner()
    elif choice == "3":
        handle_delete_user()
    else:
        print("❌ ตัวเลือกไม่ถูกต้อง")


if __name__ == "__main__":
    main()