@echo off
cd /d "%~dp0"
echo Installing required packages...
python -m pip install -q python-multipart fastapi uvicorn psycopg2-binary pandas sqlalchemy openpyxl bcrypt "python-jose[cryptography]"
echo Starting FastAPI...
echo Open http://127.0.0.1:8000/docs in your browser
python -m uvicorn fast:app --host 127.0.0.1 --port 8000 --reload
pause