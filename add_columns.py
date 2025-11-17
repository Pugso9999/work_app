import psycopg2
import os

DATABASE_URL = "postgresql://workapp_db_3nxq_user:MLCl6JbfWMEkj4GwiwOlyukMEEkzFFej@dpg-d43cdfili9vc73crdq7g.oregon-postgres.render.com/workapp_db_3nxq"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

columns = {
    "branch": "ALTER TABLE work_logs ADD COLUMN branch TEXT",
    "assigned_by": "ALTER TABLE work_logs ADD COLUMN assigned_by TEXT",
    "updated_at": "ALTER TABLE work_logs ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()",
    "created_at": "ALTER TABLE work_logs ADD COLUMN created_at TIMESTAMP DEFAULT NOW()"
}

for name, sql in columns.items():
    try:
        cur.execute(sql)
        conn.commit()
        print(f"เพิ่มคอลัมน์ {name} ✓")
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()
        print(f"คอลัมน์ {name} มีอยู่แล้ว ✓")

conn.close()
print("เสร็จแล้ว ✓")
