from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
import subprocess
import datetime
import os

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

    # สร้างตาราง work_logs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_logs (
            id SERIAL PRIMARY KEY,
            work_date TEXT NOT NULL,
            category TEXT,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'done'
        )
    """)

    # เพิ่ม column branch
    try:
        cur.execute("ALTER TABLE work_logs ADD COLUMN branch TEXT")
        conn.commit()  # commit ถ้าเพิ่มสำเร็จ
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()  # rollback ถ้า column มีอยู่แล้ว

    # เพิ่ม column assigned_by
    try:
        cur.execute("ALTER TABLE work_logs ADD COLUMN assigned_by TEXT")
        conn.commit()
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()

    # สร้างตาราง daily_checks
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

    # เพิ่ม column created_at
    try:
        cur.execute("ALTER TABLE daily_checks ADD COLUMN created_at TIMESTAMP DEFAULT NOW()")
        conn.commit()
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()

    conn.close()


# ---------------------------------
# INSERT AUTO DATA V2
# ---------------------------------
def insert_auto_data_v2():
    conn = get_db_connection()
    cur = conn.cursor()

    items = [
        "ตรวจสอบระบบ Server",
        "ตรวจสอบเครื่องสำรองไฟ (UPS)",
        "สำรวจเครื่องชั่งน้ำหนัก",
        "ตรวจสอบกล้อง CCTV",
        "สำรวจเครื่อง Cashier",
        "สำรวจคอมพิวเตอร์ห้องจุดรับสินค้า"
    ]

    start_date = datetime.date(2025, 10, 20)
    end_date = datetime.date(2025, 11, 9)
    delta = datetime.timedelta(days=1)

    current_date = start_date
    added_count = 0

    while current_date <= end_date:
        # ข้ามวันพุธ
        if current_date.weekday() == 2:
            current_date += delta
            continue

        for item in items:
            status = "ปกติ"
            if item == "ตรวจสอบระบบ Server" and current_date == datetime.date(2025, 10, 26):
                status = "ผิดปกติ"

            cur.execute("""
                INSERT INTO daily_checks (check_date, item_name, status, remark, checked_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                current_date.strftime("%Y-%m-%d"),
                item,
                status,
                "เพิ่มข้อมูลอัตโนมัติ",
                "System Bot"
            ))
            added_count += 1

        current_date += delta

    conn.commit()
    conn.close()
    print(f"✅ เพิ่มข้อมูลตรวจสอบอัตโนมัติแล้วทั้งหมด {added_count} รายการเรียบร้อย!")

# ---------------------------------
# BACKUP FUNCTION
# ---------------------------------
def auto_backup_db():
    try:
        backup_dir = os.path.join(os.path.dirname(__file__), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")

        if subprocess.call(["which", "pg_dump"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            subprocess.run(["pg_dump", DATABASE_URL, "-f", backup_file], check=True)
            print(f"[Auto Backup] ✅ สำรองฐานข้อมูลเรียบร้อย -> {backup_file}")
        else:
            print("[Auto Backup] ⚠️ ข้ามการสำรอง: Render ไม่มี pg_dump")
    except Exception as e:
        print(f"[Auto Backup Error] {e}")

# ---------------------------------
# หน้าแรก (Dashboard)
# ---------------------------------
@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()

    # ดึง branch และ assigned_by ด้วย
    cur.execute("""
        SELECT id, work_date, category, description, status, branch, assigned_by
        FROM work_logs
        ORDER BY work_date::date DESC, id DESC
    """)
    logs = cur.fetchall()

    # Summary
    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='done'")
    done = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='in progress'")
    in_progress = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='pending'")
    pending = cur.fetchone()['count']

    conn.close()

    # แปลสถานะเป็นไทย
    status_dict = {'done': 'เสร็จสิ้น', 'in progress': 'กำลังดำเนินการ', 'pending': 'รอดำเนินการ'}
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
        flash("✅ เพิ่มรายการสำเร็จ", "success")
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
            "INSERT INTO work_logs (work_date, category, description, status, branch, assigned_by) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                request.form["work_date"],
                request.form["category"],
                request.form["description"],
                request.form["status"],
                request.form.get("branch"),
                request.form.get("assigned_by")
            )
        )
        conn.commit()
        conn.close()
        auto_backup_db()
        flash("✅ เพิ่มงานเรียบร้อยแล้ว", "success")
        return redirect("/")
    return render_template("add.html", today=date.today())

# ลบงาน
@app.route("/delete/<int:id>")
def delete(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM work_logs WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    auto_backup_db()
    flash("✅ ลบงานเรียบร้อยแล้ว", "success")
    return redirect("/")

# แก้ไขงาน
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == "POST":
        cur.execute(
    "UPDATE work_logs SET work_date=%s, category=%s, description=%s, status=%s, branch=%s, assigned_by=%s WHERE id=%s",
    (
        request.form["work_date"],
        request.form["category"],
        request.form["description"],
        request.form["status"],
        request.form.get("branch"),
        request.form.get("assigned_by"),
        id
    )
)

        conn.commit()
        conn.close()
        auto_backup_db()
        flash("✅ แก้ไขงานเรียบร้อยแล้ว", "success")
        return redirect("/")
    
    cur.execute("SELECT * FROM work_logs WHERE id=%s", (id,))
    log = cur.fetchone()
    conn.close()
    return render_template("edit.html", log=log)


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
        flash("✅ เพิ่ม Switch สำเร็จ", "success")
        return redirect(url_for("switches"))

    return render_template("add_switch.html")

# ---------------------------------
# Daily Check
# ---------------------------------
@app.route("/daily_check")
def daily_check():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) AS count FROM daily_checks GROUP BY status")
    stats = cur.fetchall()
    conn.close()

    labels = [s['status'] for s in stats]
    data = [s['count'] for s in stats]

    return render_template("daily_check.html", labels=labels, data=data)

@app.route("/daily_check_stats_json")
def daily_check_stats_json():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) AS count FROM daily_checks GROUP BY status")
    stats = cur.fetchall()
    conn.close()

    labels = [s['status'] for s in stats]
    data = [s['count'] for s in stats]

    return {"labels": labels, "data": data}

@app.route("/add_daily_check", methods=["POST"])
def add_daily_check():
    check_date = request.form["check_date"]
    item_name = request.form["item_name"]
    status = request.form["status"]
    remark = request.form["remark"]
    checked_by = request.form["checked_by"]

    conn = get_db_connection()
    cur = conn.cursor()

    # ป้องกันข้อมูลซ้ำ
    cur.execute("""
        SELECT * FROM daily_checks
        WHERE check_date=%s AND item_name=%s
    """, (check_date, item_name))
    exists = cur.fetchone()
    if exists:
        flash(f"❌ ข้อมูล '{item_name}' ของวันที่ {check_date} ซ้ำ ไม่สามารถเพิ่มได้", "warning")
        conn.close()
        return redirect(url_for("daily_check"))

    cur.execute("""
        INSERT INTO daily_checks (check_date, item_name, status, remark, checked_by, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (check_date, item_name, status, remark, checked_by))
    conn.commit()
    conn.close()
    auto_backup_db()
    flash(f"✅ บันทึกข้อมูลเรียบร้อยแล้ว", "success")
    return redirect(url_for("daily_check_history"))

@app.route("/daily_check_history")
def daily_check_history():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_checks ORDER BY check_date DESC, id DESC")
    records = cur.fetchall()
    conn.close()

    return render_template("daily_check_history.html", records=records)

# ลบ Daily Check
@app.route("/delete_daily_check/<int:id>")
def delete_daily_check(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM daily_checks WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    auto_backup_db()
    flash("✅ ลบข้อมูลเรียบร้อยแล้ว", "success")
    return redirect(url_for("daily_check_history"))

# AJAX ลบ Daily Check
@app.route("/delete_daily_check_ajax/<int:id>", methods=["POST"])
def delete_daily_check_ajax(id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM daily_checks WHERE id=%s", (id,))
        conn.commit()
        conn.close()
        auto_backup_db()
        return {"success": True, "message": "✅ ลบข้อมูลเรียบร้อยแล้ว"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ---------------------------------
# RUN
# ---------------------------------
if __name__ == "__main__":
    init_db()
    insert_auto_data_v2()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=True)
