import psycopg2
from psycopg2.extras import RealDictCursor
import os

conn = psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=RealDictCursor)
cur = conn.cursor()

# สร้าง column ใหม่ถ้ายังไม่มี
cur.execute("ALTER TABLE work_logs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();")
cur.execute("ALTER TABLE work_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();")

conn.commit()
conn.close()
print("✅ Columns updated_at และ created_at พร้อมใช้งานแล้ว")
