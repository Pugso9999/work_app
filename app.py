from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
import os
import subprocess
import datetime

app = Flask(__name__)
app.secret_key = "secretkey"

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# ---------------------------------
# สร้างตาราง (ไม่ลบของเดิม)
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
# ฟังก์ชันสำรองฐานข้อมูล
# ---------------------------------
def auto_backup_db():
    try:
        backup_dir = os.path.join(os.path.dirname(__file__), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")

        subprocess.run(
            ["pg_dump", DATABASE_URL, "-f", backup_file],
            check=True
        )
        print(f"[Auto Backup] สำรองฐานข้อมูลเรียบร้อย -> {backup_file}")
    except Exception as e:
        print(f"[Auto Backup Error] {e}")


# ---------------------------------
# หน้าแรก
# ---------------------------------
@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()

    date_filter = request.args.get("date")
    status_filter = request.args.get("status")
    category_filter = request.args.get("category_filter")
    keyword = request.args.get("keyword")

    query = "SELECT id, work_date, category, description, status FROM work_logs WHERE 1=1"
    params = []

    if date_filter:
        query += " AND work_date=%s"
        params.append(date_filter)
    if status_filter:
        query += " AND status=%s"
        params.append(status_filter)
    if category_filter:
        query += " AND category=%s"
        params.append(category_filter)
    if keyword:
        query += " AND (category ILIKE %s OR description ILIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    query += " ORDER BY id DESC"
    cur.execute(query, params)
    logs = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='done'")
    done = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='in progress'")
    in_progress = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM work_logs WHERE status='pending'")
    pending = cur.fetchone()['count']

    conn.close()
    return render_template("index.html", logs=logs, done=done, in_progress=in_progress, pending=pending)


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
    return redirect("/")


# ---------------------------------
# Switch & Cameras
# ---------------------------------
@app.route("/switches")
def switches():
    conn = get_db_connection()
    cur = conn.cursor()

    # ดึง Switches ทั้งหมด
    cur.execute("SELECT * FROM switches ORDER BY id DESC")
    switches = cur.fetchall()

    # ดึงกล้องทั้งหมด และรวมกับ switch
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

        # กล้อง
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


@app.route("/edit_switch/<int:id>", methods=["GET", "POST"])
def edit_switch(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            UPDATE switches
            SET name=%s, ip=%s, model=%s, ports=%s, location=%s, status=%s, remark=%s
            WHERE id=%s
        """, (
            request.form.get("name"),
            request.form.get("ip"),
            request.form.get("model"),
            int(request.form.get("ports") or 0),
            request.form.get("location"),
            request.form.get("status"),
            request.form.get("remark"),
            id
        ))
        # อัพเดทกล้อง: ลบกล้องเดิมก่อน แล้วเพิ่มใหม่
        cur.execute("DELETE FROM cameras WHERE switch_id=%s", (id,))
        names = request.form.getlist('camera_name[]')
        ips = request.form.getlist('camera_ip[]')
        for n, i in zip(names, ips):
            if i:
                cur.execute("INSERT INTO cameras (switch_id, name, ip) VALUES (%s, %s, %s)", (id, n, i))

        conn.commit()
        conn.close()
        auto_backup_db()
        flash("แก้ไข Switch สำเร็จ", "success")
        return redirect(url_for("switches"))

    # GET method
    cur.execute("SELECT * FROM switches WHERE id=%s", (id,))
    switch = cur.fetchone()
    cur.execute("SELECT * FROM cameras WHERE switch_id=%s", (id,))
    cameras = cur.fetchall()
    conn.close()
    return render_template("edit_switch.html", switch=switch, cameras=cameras)


@app.route("/delete_switch/<int:id>")
def delete_switch(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM switches WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    auto_backup_db()
    flash("ลบ Switch สำเร็จ", "success")
    return redirect(url_for("switches"))


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
        subprocess.run(
            ["psql", DATABASE_URL, "-f", file_path],
            check=True
        )
        flash(f"คืนค่าฐานข้อมูลจาก {latest} สำเร็จ", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการคืนค่า: {e}", "danger")
    return redirect("/")


# ---------------------------------
# Run Flask App
# ---------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
