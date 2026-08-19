@echo off
cd /d "%~dp0"

if not exist ".env" (
    echo [WARNING] ไม่พบไฟล์ .env ในโฟลเดอร์นี้
    echo กรุณา copy .env.example -^> .env แล้วกรอกรหัสผ่าน Supabase ก่อนรัน
    pause
    exit /b 1
)

echo Installing required packages...
python -m pip install -q python-multipart fastapi uvicorn psycopg2-binary pandas sqlalchemy python-dotenv openpyxl
echo Starting FastAPI...
echo Open http://127.0.0.1:8000/docs in your browser
python -m uvicorn fast:app --host 127.0.0.1 --port 8000 --reload
pause
