-- ==========================================================
-- Threshold reference table
-- ==========================================================
-- เก็บค่า Maximum/Minimum threshold ของแต่ละ metric ต่อ
-- Measure Object หนึ่งตัว โดยดึงมาจาก sheet ต่อไปนี้ใน Excel:
--   Control Ratio, Fan Ratio, MSU, Line board, Client board
--
-- ค่าที่อยู่ใน sheet จะถูกทำซ้ำในทุกช่วงวันที่ (7/8/2026, 7/16/2026, ...)
-- เพราะ threshold เป็นค่าคงที่ต่ออุปกรณ์/พอร์ต ไม่ใช่ time-series
-- ดังนั้นตารางนี้เก็บแค่ "ค่าล่าสุดที่ import" ต่อ 1 metric/1 measure_object
-- (ไม่ใช่ time-series เหมือนตาราง *_performance)
-- ==========================================================

CREATE TABLE IF NOT EXISTS "thresholds" (
    id              SERIAL PRIMARY KEY,

    -- ที่มาของค่า
    source_sheet    VARCHAR(100)  NOT NULL,   -- ชื่อ sheet ต้นทาง เช่น 'Fan Ratio'
    metric_key      VARCHAR(150)  NOT NULL,   -- ชื่อ metric ที่ normalize แล้ว เช่น 'fan_speed'
    metric_label    VARCHAR(200),             -- header ดิบจากไฟล์ เช่น 'Value of Fan Rotate Speed(Rps)'
    unit            VARCHAR(50),              -- หน่วย เช่น 'Rps', 'dBm', 'mA', '%'

    -- ตัวระบุอุปกรณ์ / พอร์ต (ใช้ join กับตาราง *_performance ที่มีอยู่แล้ว)
    site_name       VARCHAR(200),
    me_name         VARCHAR(200)  NOT NULL,   -- ตรงกับคอลัมน์ me_name ในตาราง performance
    me_ip           VARCHAR(50),              -- อาจไม่มีใน sheet threshold บาง sheet จึงปล่อยว่างได้
    measure_object  VARCHAR(300)  NOT NULL,   -- ตรงกับคอลัมน์ measure_object ในตาราง performance

    -- แตกรายละเอียดจาก measure_object เหมือนที่ fast.py ทำกับตาราง performance
    board_name      VARCHAR(200),
    location_path   VARCHAR(100),
    sub_function    VARCHAR(200),

    -- ค่า threshold
    min_threshold   NUMERIC,
    max_threshold   NUMERIC,

    source_date     DATE,                     -- วันที่ (คอลัมน์กลุ่มวันที่) ที่ค่านี้ถูกอ่านมาล่าสุด
    updated_at      TIMESTAMP NOT NULL DEFAULT now(),

    -- 1 metric ต่อ 1 measure_object ต่อ 1 ME ควรมีค่าเดียว
    CONSTRAINT uq_threshold UNIQUE (metric_key, me_name, measure_object)
);

-- ให้ค้นหาเร็วตอน join กับตาราง performance ด้วย me_ip / measure_object
CREATE INDEX IF NOT EXISTS idx_thresholds_metric_meip
    ON "thresholds" (metric_key, me_ip);

CREATE INDEX IF NOT EXISTS idx_thresholds_measure_object
    ON "thresholds" (measure_object);
