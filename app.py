from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
import os
import subprocess
import datetime

app = Flask(__name__)
app.secret_key = "secretkey"

# ---------------------------------
# DATABASE CONFIG
# ---------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL not found. Please set in Render Environment Variables.")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


# ---------------------------------
# INITIALIZE TABLES
# ---------------------------------
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_logs (
            id SERIAL PRIMARY KEY,
            work_date TEXT NOT NULL,
            category TEXT,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'done'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_checks (
            id SERIAL PRIMARY KEY,
            check_date TEXT,
            item_name TEXT,
            status TEXT,
            remark TEXT,
            checked_by TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            item_name TEXT NOT NULL,
            category TEXT,
            quantity INTEGER DEFAULT 0,
            location TEXT,
            remark TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS switches (
            id SERIAL PRIMARY KEY,
            name TEXT,
            ip TEXT,
            model TEXT,
            ports INTEGER,
            location TEXT,
            status TEXT,
            remark TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            id SERIAL PRIMARY KEY,
            switch_id INTEGER REFERENCES switches(id) ON DELETE CASCADE,
            name TEXT,
            ip TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------------------------
# BACKUP FUNCTION (safe mode for Render)
# ---------------------------------
def auto_backup_db():
    try:
        backup_dir = os.path.join(os.path.dirname(__file__), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")

        # Check if pg_dump exists (Render may not have it)
        if subprocess.call(["which", "pg_dump"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            subprocess.run(["pg_dump", DATABASE_URL, "-f", backup_file], check=True)
            print(f"[Auto Backup] สำรองฐานข้อมูลเรียบร้อย -> {backup_file}")
        else:
            print("[Auto Backup] ⚠️ ข้ามการสำรอง: Render ไม่มี pg_dump")
    except Exception as e:
        print(f"[Auto Backup Error] {e}")


# ---------------------------------
# หน้าแรก
# ---------------------------------
@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, work_date, category, description, status FROM work_logs ORDER BY work_date::date DESC, id DESC")
    logs = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='done'")
    done = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='in progress'")
    in_progress = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='pending'")
    pending = cur.fetchone()['count']

    conn.close()

    status_dict = {
        'done': 'เสร็จสิ้น',
        'in progress': 'กำลังดำเนินการ',
        'pending': 'รอดำเนินการ'
    }

    for log in logs:
        log['status_th'] = status_dict.get(log['status'], log['status'])

    return render_template("index.html", logs=logs, done=done, in_progress=in_progress, pending=pending)


# ---------------------------------
# Inventory
# ---------------------------------
@app.route("/inventory")
def inventory():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM inventory ORDER BY id DESC")
    items = cur.fetchall()
    conn.close()
    return render_template("inventory.html", items=items)


@app.route("/add_inventory", methods=["GET", "POST"])
def add_inventory():
    if request.method == "POST":
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO inventory (item_name, category, quantity, location, remark)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            request.form["item_name"],
            request.form.get("category"),
            request.form.get("quantity") or 0,
            request.form.get("location"),
            request.form.get("remark")
        ))
        conn.commit()
        conn.close()
        auto_backup_db()
        flash("เพิ่มรายการสำเร็จ", "success")
        return redirect(url_for("inventory"))
    return render_template("add_inventory.html")


# ---------------------------------
# เพิ่มงาน
# ---------------------------------
@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO work_logs (work_date, category, description, status) VALUES (%s, %s, %s, %s)",
            (request.form["work_date"], request.form["category"], request.form["description"], request.form["status"])
        )
        conn.commit()
        conn.close()
        auto_backup_db()
        return redirect("/")
    return render_template("add.html", today=date.today())


# ---------------------------------
# แก้ไข / ลบ งาน
# ---------------------------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == "POST":
        cur.execute(
            "UPDATE work_logs SET work_date=%s, category=%s, description=%s, status=%s WHERE id=%s",
            (request.form["work_date"], request.form["category"], request.form["description"], request.form["status"], id)
        )
        conn.commit()
        conn.close()
        auto_backup_db()
        return redirect("/")

    cur.execute("SELECT * FROM work_logs WHERE id=%s", (id,))
    log = cur.fetchone()
    conn.close()
    return render_template("edit.html", log=log)


@app.route("/delete/<int:id>")
def delete(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM work_logs WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    auto_backup_db()
    flash("ลบงานเรียบร้อยแล้ว", "success")
    return redirect("/")


# ---------------------------------
# Switch & Cameras
# ---------------------------------
@app.route("/switches")
def switches():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM switches ORDER BY id DESC")
    switches = cur.fetchall()

    cur.execute("SELECT * FROM cameras")
    cameras = cur.fetchall()
    camera_dict = {}
    for cam in cameras:
        camera_dict.setdefault(cam['switch_id'], []).append(cam)

    conn.close()
    return render_template("switches.html", switches=switches, camera_dict=camera_dict)


@app.route("/add_switch", methods=["GET", "POST"])
def add_switch():
    if request.method == "POST":
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO switches (name, ip, model, ports, location, status, remark)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (
            request.form.get("name"),
            request.form.get("ip"),
            request.form.get("model"),
            request.form.get("ports") or 0,
            request.form.get("location"),
            request.form.get("status"),
            request.form.get("remark")
        ))
        switch_id = cur.fetchone()['id']

        names = request.form.getlist('camera_name[]')
        ips = request.form.getlist('camera_ip[]')
        for n, i in zip(names, ips):
            if i:
                cur.execute("INSERT INTO cameras (switch_id, name, ip) VALUES (%s, %s, %s)", (switch_id, n, i))

        conn.commit()
        conn.close()
        auto_backup_db()
        flash("เพิ่ม Switch สำเร็จ", "success")
        return redirect(url_for("switches"))

    return render_template("add_switch.html")


# ---------------------------------
# ตรวจสอบประจำวัน
# ---------------------------------
@app.route("/daily_check")
def daily_check():
    return render_template("daily_check.html")


@app.route("/add_daily_check", methods=["POST"])
def add_daily_check():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO daily_checks (check_date, item_name, status, remark, checked_by)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        request.form["check_date"],
        request.form["item_name"],
        request.form["status"],
        request.form["remark"],
        request.form["checked_by"]
    ))
    conn.commit()
    conn.close()
    auto_backup_db()
    flash("บันทึกข้อมูลเรียบร้อยแล้ว", "success")
    return redirect(url_for("daily_check"))


@app.route("/daily_check_history")
def daily_check_history():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_checks ORDER BY id DESC")
    checks = cur.fetchall()
    conn.close()
    return render_template("daily_check_history.html", checks=checks)


# ---------------------------------
# คืนค่าฐานข้อมูลจากไฟล์ล่าสุด
# ---------------------------------
@app.route("/admin/restore_latest")
def restore_latest():
    try:
        backup_dir = os.path.join(os.path.dirname(__file__), "backups")
        files = [f for f in os.listdir(backup_dir) if f.endswith(".sql")]
        if not files:
            flash("ไม่พบไฟล์สำรอง", "warning")
            return redirect("/")
        latest = max(files)
        file_path = os.path.join(backup_dir, latest)
        subprocess.run(["psql", DATABASE_URL, "-f", file_path], check=True)
        flash(f"คืนค่าฐานข้อมูลจาก {latest} สำเร็จ", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการคืนค่า: {e}", "danger")
    return redirect("/")


# ---------------------------------
# INSERT AUTO DATA
# ---------------------------------
@app.route("/insert_auto_data")
def insert_auto_data():
    conn = get_db_connection()
    cur = conn.cursor()

    items = [
        "ตรวจสอบระบบ Server",
        "ตรวจสอบกล้อง CCTV",
        "ตรวจสอบสวิตช์เครือข่าย",
        "ตรวจสอบเครื่องสำรองไฟ (UPS)",
        "ตรวจสอบระบบอินเทอร์เน็ต",
        "ตรวจสอบอุปกรณ์สำนักงาน",
        "ตรวจสอบเครื่องพิมพ์",
        "ตรวจสอบระบบแสงสว่าง",
        "ตรวจสอบอุณหภูมิห้อง Server",
        "ตรวจสอบระบบ NAS สำรองข้อมูล"
    ]

    statuses = ["ปกติ", "ผิดปกติ", "รอตรวจสอบ"]

    start_date = datetime.date(2025, 10, 20)
    end_date = datetime.date(2025, 11, 6)
    delta = datetime.timedelta(days=1)

    current_date = start_date
    added_count = 0

    while current_date <= end_date:
        for item in items:
            cur.execute("""
                INSERT INTO daily_checks (check_date, item_name, status, remark, checked_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                current_date.strftime("%Y-%m-%d"),
                item,
                statuses[added_count % len(statuses)],
                "ข้อมูลอัตโนมัติ",
                "System Bot"
            ))
            added_count += 1
        current_date += delta

    conn.commit()
    conn.close()
    auto_backup_db()
    return f"✅ เพิ่มข้อมูลอัตโนมัติแล้วทั้งหมด {added_count} รายการเรียบร้อย!"


# ---------------------------------
# RUN
# ---------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=True)
