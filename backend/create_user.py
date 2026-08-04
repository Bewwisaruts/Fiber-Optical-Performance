import getpass
from auth import create_user, get_user

def main():
    print("=== สร้างผู้ใช้งานใหม่ (Fiber Dashboard) ===")
    username = input("Username: ").strip()

    if get_user(username):
        print(f"❌ Username '{username}' มีอยู่แล้วในระบบ")
        return

    password = getpass.getpass("Password: ")
    password_confirm = getpass.getpass("Confirm Password: ")
    if password != password_confirm:
        print("❌ รหัสผ่านไม่ตรงกัน")
        return

    full_name = input("Full name (ไม่บังคับ): ").strip()
    role = input("Role [admin/viewer] (default: admin): ").strip() or "admin"

    create_user(username=username, password=password, full_name=full_name, role=role)
    print(f"✅ สร้างผู้ใช้ '{username}' (role: {role}) สำเร็จ")

if __name__ == "__main__":
    main()