from fastapi import FastAPI, Query, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from sqlalchemy import create_engine, text
import io
import re

app = FastAPI(title="Network Performance API (Enterprise Version)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. Database Configuration
# ==========================================
DB_USER = "postgres"
DB_PASSWORD = "bew30012548"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "Client-Card"

connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(connection_string)

def get_db_connection():
    return psycopg2.connect(
        user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT, database=DB_NAME
    )

# ==========================================
# 2. Base Configuration & Table Registry
# ==========================================
# ส่วนกลางสำหรับคอลัมน์ที่มีในทุกๆ ไฟล์ Performance
BASE_PERF_MAPPING = {
    'Begin Time': 'begin_time', 'End Time': 'end_time', 'Granularity': 'granularity',
    'ME': 'me_name', 'ME IP': 'me_ip', 'Measure Object': 'measure_object'
}

# Registry ตรวจสอบไฟล์อัตโนมัติ (ชื่อตารางอ้างอิงตามฐานข้อมูลจริง)
TABLE_REGISTRY = {
    "alarm_history": {
        "table_name": "fm-history",
        "file_keyword": "fm-history",
        "required_columns": ["Alarm ID", "Occurrence Time", "Alarm Code"],
        "conflict_target": "alarm_id",
        "is_performance": False,
        "mapping": {
            'Alarm ID': 'alarm_id', 'ME': 'me_name', 'ME IP': 'me_ip',
            'Alarm Code': 'alarm_code', 'Alarm Code Name': 'alarm_code_name',
            'Alarm Severity': 'alarm_severity', 'Occurrence Time': 'occurrence_time',
            'Clear Time': 'clear_time', 'Duration Time': 'duration_time'
        }
    },
    "cpu_perf": {
        "table_name": "cpu_performance",
        "file_keyword": "CPU ratio",
        "required_columns": ["Max CPU utilization ratio", "CPU utilization ratio", "RAM utilization ratio"],
        "conflict_target": "begin_time, me_ip, measure_object",
        "is_performance": True,
        "mapping": {**BASE_PERF_MAPPING, **{
            'Max CPU utilization ratio': 'cpu_max_ratio', 'Min CPU utilization ratio': 'cpu_min_ratio',
            'CPU utilization ratio': 'cpu_avg_ratio', 'RAM utilization ratio': 'ram_avg_ratio',
            'Max RAM utilization ratio': 'ram_max_ratio', 'Min RAM utilization ratio': 'ram_min_ratio'
        }}
    },
    "client_card_perf": {
        "table_name": "client-card_performance",
        "file_keyword": "Client card performance",
        "required_columns": ["Max Value of Output Optical Power(dBm)", "Output Optical Power (dBm)"],
        "conflict_target": "begin_time, me_ip, measure_object",
        "is_performance": True,
        "mapping": {**BASE_PERF_MAPPING, **{
            'Max Value of Output Optical Power(dBm)': 'max_out_power', 'Min Value of Output Optical Power(dBm)': 'min_out_power',
            'Input Optical Power(dBm)': 'input_power', 'Output Optical Power (dBm)': 'output_power'
        }}
    },
    "fan_perf": {
        "table_name": "fan_performance",
        "file_keyword": "FAN ratio",
        "required_columns": ["Value of Fan Rotate Speed(Rps)"],
        "conflict_target": "begin_time, me_ip, measure_object",
        "is_performance": True,
        "mapping": {**BASE_PERF_MAPPING, **{
            'Max Value of Fan Rotate Speed(Rps)': 'max_fan_speed', 'Min Value of Fan Rotate Speed(Rps)': 'min_fan_speed',
            'Value of Fan Rotate Speed(Rps)': 'fan_speed'
        }}
    },
    "line_card_perf": {
        "table_name": "line-card_performance",
        "file_keyword": "Line cards performance",
        "required_columns": ["Instant BER After FEC", "Instant BER Before FEC"],
        "conflict_target": "begin_time, me_ip, measure_object",
        "is_performance": True,
        "mapping": {**BASE_PERF_MAPPING, **{
            'Instant BER After FEC': 'ber_after_fec', 'Instant BER Before FEC': 'ber_before_fec',
            'Input Optical Power(dBm)': 'input_power', 'Output Optical Power (dBm)': 'output_power'
        }}
    },
    "msu_perf": {
        "table_name": "msu_performance",
        "file_keyword": "MSU performance",
        "required_columns": ["Laser Bias Current(mA)"],
        "conflict_target": "begin_time, me_ip, measure_object",
        "is_performance": True,
        "mapping": {**BASE_PERF_MAPPING, **{
            'Max Value of Laser Bias Current(mA)': 'max_laser_current', 'Min Value of Laser Bias Current(mA)': 'min_laser_current', 
            'Laser Bias Current(mA)': 'laser_current'
        }}
    },
    "osc_power": {
        "table_name": "osc_performance",
        "file_keyword": "OSC Power Flapping",
        "required_columns": ["Max Value of Input Optical Power(dBm)", "Input Optical Power(dBm)"],
        "conflict_target": "begin_time, me_ip, measure_object",
        "is_performance": True,
        "mapping": {**BASE_PERF_MAPPING, **{
            'Max Value of Input Optical Power(dBm)': 'max_input_power', 'Min Value of Input Optical Power(dBm)': 'min_input_power',
            'Input Optical Power(dBm)': 'input_power'
        }}
    }
}

# ==========================================
# 3. Helper Functions
# ==========================================
def extract_measure_object_details(df: pd.DataFrame) -> pd.DataFrame:
    """ ฟังก์ชันสกัดข้อมูลบอร์ดและพอร์ตจากคอลัมน์ measure_object """
    if 'measure_object' in df.columns:
        df['board_name'] = df['measure_object'].str.extract(r'^([^\[]+)')
        df['location_path'] = df['measure_object'].str.extract(r'\[([0-9-]+)\]')
        df['sub_function'] = df['measure_object'].str.extract(r'\]-([^:(]+)')
    return df

def execute_pg_upsert(df: pd.DataFrame, table_name: str, conflict_target: str):
    """ ฟังก์ชันบันทึกข้อมูลเข้าฐานข้อมูลแบบกันข้อมูลซ้ำ (Upsert) """
    staging_table = f"temp_staging_{table_name.replace('-', '_')}"
    
    # เพิ่ม " รอบชื่อคอลัมน์ เพื่อรองรับอักษรพิมพ์เล็ก-ใหญ่ใน PostgreSQL อย่างถูกต้อง
    columns_str = ", ".join([f'"{c}"' for c in df.columns])
    
    with engine.begin() as conn:
        # 1. นำข้อมูลไปพักที่ Staging Table
        df.to_sql(name=staging_table, con=conn, if_exists='replace', index=False, method='multi', chunksize=5000)
        
        # 2. Insert เข้าตารางจริง หากซ้ำให้ข้าม (DO NOTHING)
        upsert_sql = f"""
            INSERT INTO "{table_name}" ({columns_str})
            SELECT {columns_str} FROM "{staging_table}"
            ON CONFLICT ({conflict_target}) 
            DO NOTHING;
        """
        conn.execute(text(upsert_sql))
        
        # 3. ลบตารางพักข้อมูลทิ้ง
        conn.execute(text(f'DROP TABLE IF EXISTS "{staging_table}";'))


# ==========================================
# 4. API Endpoints
# ==========================================
@app.get("/api/metrics")
def get_network_metrics(me_ip: str = Query(..., description="ไอพีของอุปกรณ์เครือข่าย")):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # ดึงจากตาราง cpu_performance เป็นหลัก
        query = """
            SELECT 
                begin_time, me_name, me_ip,
                ROUND((cpu_avg_ratio * 100)::numeric, 2) as cpu_percent,
                ROUND((ram_avg_ratio * 100)::numeric, 2) as ram_percent
            FROM "cpu_performance"
            WHERE me_ip = %s ORDER BY begin_time ;
        """
        cursor.execute(query, (me_ip,))
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"status": "success", "total_records": len(data), "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/data")
def get_all_data(table_name: str = Query("cpu_performance", description="ชื่อตารางที่ต้องการดึงข้อมูล")):
    """ Endpoint สำหรับดึงข้อมูลจากตารางที่ต้องการไปแสดงหน้าเว็บ """
    # ตรวจสอบความปลอดภัย ป้องกัน SQL Injection
    allowed_tables = [config["table_name"] for config in TABLE_REGISTRY.values()]
    if table_name not in allowed_tables:
        return {"status": "error", "message": "ไม่อนุญาตให้เข้าถึงตารางนี้"}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # ค้นหาคอลัมน์เวลาของตารางนั้นๆ (เพื่อจัดเรียง)
        order_col = "occurrence_time" if table_name == "fm-history" else "begin_time"
        
        query = f'SELECT * FROM "{table_name}" ORDER BY "{order_col}" '
        cursor.execute(query)
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"status": "success", "table": table_name, "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/upload")
async def upload_file_automated(file: UploadFile = File(...)):
    # ป้องกัน OOM: จำกัดขนาดไฟล์อัปโหลดไว้ไม่เกิน 50MB
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="ไฟล์มีขนาดใหญ่เกินไป (จำกัดไม่เกิน 50MB)")
        
    try:
        filename = file.filename
        df = pd.read_excel(io.BytesIO(contents))
        uploaded_columns = set(df.columns.tolist())
        
        matched_key = None
        
        # สเต็ปที่ 1: ตรวจสอบจากชื่อไฟล์ + เช็คโครงสร้างคร่าวๆ
        for key, config in TABLE_REGISTRY.items():
            if config["file_keyword"].lower() in filename.lower():
                if all(col in uploaded_columns for col in config["required_columns"]):
                    matched_key = key
                    break
        
        # สเต็ปที่ 2: กรณีชื่อไฟล์ถูกเปลี่ยน ค้นหาจากคะแนนลายเซ็นของคอลัมน์แทน
        if not matched_key:
            best_score = 0
            for key, config in TABLE_REGISTRY.items():
                if all(col in uploaded_columns for col in config["required_columns"]):
                    score = len(set(config["required_columns"]).intersection(uploaded_columns))
                    if score > best_score:
                        best_score = score
                        matched_key = key

        if not matched_key:
            raise HTTPException(
                status_code=400, 
                detail="ไม่สามารถระบุประเภทไฟล์ได้ โครงสร้างคอลัมน์ไม่ตรงกับตารางใดๆ ในระบบ"
            )
            
        # เริ่มกระบวนการ Mapping และทำความสะอาดข้อมูล
        target_config = TABLE_REGISTRY[matched_key]
        target_table = target_config["table_name"]
        
        # เปลี่ยนชื่อคอลัมน์
        df = df.rename(columns=target_config["mapping"])
        
        # แปลงข้อมูลเวลา
        for time_col in ['begin_time', 'end_time', 'occurrence_time', 'clear_time']:
            if time_col in df.columns:
                df[time_col] = pd.to_datetime(df[time_col])
        
        exclude_numeric_cols = [
            'begin_time', 'end_time', 'occurrence_time', 'clear_time', 
            'me_name', 'me_ip', 'measure_object', 'alarm_id', 
            'alarm_code', 'alarm_code_name', 'alarm_severity'
        ]

        for col in df.columns:
            if col not in exclude_numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        # เพิ่มคอลัมน์ Board, Location ถ้าเป็นไฟล์ประสิทธิภาพ
        if target_config["is_performance"]:
            df = extract_measure_object_details(df)
            
        # จัดการค่าว่าง
        df = df.where(pd.notnull(df), None)
        
        # กรองเฉพาะคอลัมน์ที่จะใช้
        allowed_db_columns = list(target_config["mapping"].values())
        if target_config["is_performance"]:
            allowed_db_columns.extend(['board_name', 'location_path', 'sub_function'])
            
        final_columns = [col for col in allowed_db_columns if col in df.columns]
        df = df[final_columns]
        
        # อัปโหลดเข้า Database แบบป้องกันข้อมูลซ้ำ
        execute_pg_upsert(
            df=df, 
            table_name=target_table, 
            conflict_target=target_config["conflict_target"]
        )
        
        return {
            "status": "success",
            "filename": filename,
            "detected_table": target_table,
            "inserted_rows": len(df),
            "message": f"ระบบนำข้อมูลเข้าสู่ตาราง '{target_table}' สำเร็จเรียบร้อย!"
        }
        
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        return {"status": "error", "message": f"การประมวลผลล้มเหลว: {str(e)}"}

# ==========================================
# สั่งรัน uvicorn: uvicorn fast:app --reload
# ==========================================