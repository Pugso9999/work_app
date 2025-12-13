from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime, timedelta
import subprocess
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

    # ตาราง work_logs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_logs (
            id SERIAL PRIMARY KEY,
            work_date TEXT NOT NULL,
            category TEXT,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'done'
        )
    """)

    # เพิ่ม column branch, assigned_by, updated_at, created_at
    for col, sql in [
        ("branch", "ALTER TABLE work_logs ADD COLUMN branch TEXT"),
        ("assigned_by", "ALTER TABLE work_logs ADD COLUMN assigned_by TEXT"),
        ("updated_at", "ALTER TABLE work_logs ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()"),
        ("created_at", "ALTER TABLE work_logs ADD COLUMN created_at TIMESTAMP DEFAULT NOW()")
    ]:
        try:
            cur.execute(sql)
            conn.commit()
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()

    # ตาราง daily_checks
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
    # ตาราง inventory
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

    # ตาราง switches
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

    # ตาราง cameras
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            id SERIAL PRIMARY KEY,
            switch_id INTEGER REFERENCES switches(id) ON DELETE CASCADE,
            name TEXT,
            ip TEXT
        )
    """)


   # --------------------------------------------
    # ⭐ CREATE knowledge base tables (ถูกต้อง)
    # --------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS solutions_categories_all (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS solutions (
            id SERIAL PRIMARY KEY,
            category_id INTEGER REFERENCES solutions_categories_all(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            detail TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ---------------------------------
# INSERT AUTO DATA V2
# ---------------------------------

@app.route("/insert_auto_data_v2")
def insert_auto_data_v2():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # รายการตรวจสอบ
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

        # สถานะตัวอย่าง
        statuses = ["ปกติ", "ผิดปกติ", "รอตรวจสอบ"]

        # กำหนดช่วงวันที่
        start_date = date(2025, 10, 20)
        end_date = date(2025, 11, 6)
        delta = timedelta(days=1)

        current_date = start_date
        added_count = 0

        # loop เพิ่มข้อมูลอัตโนมัติ
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

        # สำรองฐานข้อมูลอัตโนมัติ
        auto_backup_db()

        return f"✅ เพิ่มข้อมูลอัตโนมัติแล้วทั้งหมด {added_count} รายการเรียบร้อย!"
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาด: {e}"

# ---------------------------------
# BACKUP FUNCTION
# ---------------------------------
def auto_backup_db():
    try:
        backup_dir = os.path.join(os.path.dirname(__file__), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

    status_dict = {'done': 'เสร็จสิ้น', 'in progress': 'กำลังดำเนินการ', 'pending': 'รอดำเนินการ'}
    for log in logs:
        log['status_th'] = status_dict.get(log['status'], log['status'])

    now = datetime.now()
    return render_template("index.html", logs=logs, done=done, in_progress=in_progress, pending=pending, now=now)

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

@app.route("/edit_item/<int:id>", methods=["GET", "POST"])
def edit_item(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            UPDATE inventory
            SET item_name=%s, category=%s, quantity=%s, location=%s, remark=%s
            WHERE id=%s
        """, (
            request.form.get("item_name"),
            request.form.get("category"),
            request.form.get("quantity"),
            request.form.get("location"),
            request.form.get("remark"),
            id
        ))
        conn.commit()
        conn.close()
        flash("แก้ไขข้อมูลอุปกรณ์สำเร็จ", "success")
        return redirect(url_for("inventory"))

    cur.execute("SELECT * FROM inventory WHERE id=%s", (id,))
    item = cur.fetchone()
    conn.close()
    return render_template("edit_item.html", item=item)


# ---------------------------------
# เพิ่มงาน
# ---------------------------------
@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO work_logs (work_date, category, description, status, branch, assigned_by)
VALUES (%s, %s, %s, %s, %s, %s)

        """, (
            request.form["work_date"],
            request.form["category"],
            request.form["description"],
            request.form["status"],
            request.form.get("branch"),
            request.form.get("assigned_by")
        ))
        conn.commit()
        conn.close()
        auto_backup_db()
        flash("✅ เพิ่มงานเรียบร้อยแล้ว", "success")
        return redirect("/")
    return render_template("add.html", today=date.today())

# ---------------------------------
# แก้ไขงาน
# ---------------------------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        # ดึงค่าจาก form และกำหนด default หากไม่มีค่า
        work_date = request.form.get("work_date", str(date.today()))
        category = request.form.get("category", "")
        description = request.form.get("description", "")
        status = request.form.get("status", "done")

        try:
            # แปลง id เป็น int เผื่อมีปัญหา
            id = int(id)

            # UPDATE ข้อมูล
            cur.execute("""
            UPDATE work_logs
            SET work_date=%s,
            category=%s,
            description=%s,
            status=%s,
            branch=%s,
            assigned_by=%s,
            updated_at=NOW()
            WHERE id=%s
            """, (
            request.form.get("work_date"),
            request.form.get("category"),
            request.form.get("description"),
            request.form.get("status"),
            request.form.get("branch"),
            request.form.get("assigned_by"),
            id
            ))
            conn.commit()
            auto_backup_db()
            flash("แก้ไขงานเรียบร้อยแล้ว", "success")
        except Exception as e:
            conn.rollback()
            flash(f"เกิดข้อผิดพลาดในการแก้ไข: {e}", "danger")
        finally:
            conn.close()
        return redirect("/")

    # GET request: แสดง form
    try:
        cur.execute("SELECT * FROM work_logs WHERE id=%s", (id,))
        log = cur.fetchone()
    except Exception as e:
        flash(f"ไม่พบงานที่ต้องการแก้ไข: {e}", "danger")
        log = None
    finally:
        conn.close()

    return render_template("edit.html", log=log)

# ---------------------------------
# ลบงาน
# ---------------------------------
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

@app.route("/switches/edit/<int:id>", methods=["GET", "POST"])
def edit_switch(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        name = request.form["name"]
        ip = request.form["ip"]
        model = request.form["model"]
        ports = request.form["ports"]
        location = request.form["location"]
        status = request.form["status"]
        remark = request.form["remark"]

        # อัปเดต switch หลัก
        cur.execute("""
            UPDATE switches
            SET name=%s, ip=%s, model=%s, ports=%s, location=%s, status=%s, remark=%s
            WHERE id=%s
        """, (name, ip, model, ports, location, status, remark, id))

        # อัปเดต cameras (ลบของเก่า → ใส่ใหม่)
        cur.execute("DELETE FROM cameras WHERE switch_id=%s", (id,))

        cam_names = request.form.getlist("camera_name[]")
        cam_ips = request.form.getlist("camera_ip[]")

        for cname, cip in zip(cam_names, cam_ips):
            if cip.strip() != "":
                cur.execute("""
                    INSERT INTO cameras (switch_id, name, ip)
                    VALUES (%s, %s, %s)
                """, (id, cname, cip))

        conn.commit()
        cur.close()
        conn.close()

        flash("อัปเดต Switch สำเร็จ", "success")
        return redirect(url_for("switches"))

    # GET: โหลดข้อมูลเดิม
    cur.execute("SELECT * FROM switches WHERE id=%s", (id,))
    sw = cur.fetchone()

    cur.execute("SELECT * FROM cameras WHERE switch_id=%s", (id,))
    cams = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("edit_switch.html", sw=sw, cams=cams)


@app.route("/delete_switch/<int:id>")
def delete_switch(id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM switches WHERE id=%s", (id,))
    cur.execute("DELETE FROM cameras WHERE switch_id=%s", (id,))
    conn.commit()
    conn.close()

    flash("ลบ Switch เรียบร้อยแล้ว", "success")
    return redirect(url_for("switches"))


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
# Knowledge Base: Categories
# ---------------------------------
# ตัวอย่าง route
@app.route("/solutions_categories_all/<int:category_id>")
def solutions_categories(category_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM solutions_categories_all WHERE id=%s", (category_id,))
    category = cur.fetchone()  # เอา category เดียว

    cur.execute("SELECT * FROM solutions WHERE category_id=%s ORDER BY id DESC", (category_id,))
    solutions = cur.fetchall()
    conn.close()

    return render_template("solutions_categories_all.html",
                           category=category,
                           solutions=solutions)


@app.route("/add_solutions/<int:category_id>", methods=["GET", "POST"])
def add_solutions(category_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # 🔒 เช็คว่า category มีอยู่จริง
    cur.execute(
        "SELECT id FROM solution_categories_all WHERE id = %s",
        (category_id,)
    )
    category = cur.fetchone()

    if not category:
        cur.close()
        conn.close()
        flash("ไม่พบหมวดหมู่นี้ หรือถูกลบไปแล้ว", "danger")
        return redirect(url_for("solutions_categories_all"))

    if request.method == "POST":
        title = request.form.get("title")
        detail = request.form.get("detail")

        if not title or not detail:
            flash("กรุณากรอกข้อมูลให้ครบ", "warning")
            return redirect(url_for("add_solutions", category_id=category_id))

        try:
            cur.execute("""
                INSERT INTO solutions (category_id, title, detail)
                VALUES (%s, %s, %s)
            """, (category_id, title, detail))

            conn.commit()
            flash("เพิ่มวิธีแก้ปัญหาสำเร็จ", "success")

        except Exception as e:
            conn.rollback()
            flash("เกิดข้อผิดพลาดในการบันทึกข้อมูล", "danger")
            print(e)

        finally:
            cur.close()
            conn.close()

        return redirect(url_for("solutions", category_id=category_id))

    cur.close()
    conn.close()
    return render_template("add_solutions.html", category_id=category_id)





# แก้ไข Solution
@app.route("/solutions/edit/<int:id>", methods=["GET", "POST"])
def edit_solutions(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT id, category_id, title, detail FROM solutions WHERE id=%s",
        (id,)
    )
    solution = cur.fetchone()

    if not solution:
        flash("ไม่พบวิธีแก้ปัญหานี้", "danger")
        return redirect(url_for("solutions_categories_all"))

    if request.method == "POST":
        title = request.form["title"]
        detail = request.form["detail"]

        cur.execute(
            "UPDATE solutions SET title=%s, detail=%s WHERE id=%s",
            (title, detail, id)
        )
        conn.commit()
        cur.close()
        conn.close()

        flash("แก้ไขเรียบร้อยแล้ว", "success")
        return redirect(url_for(
            "solutions",
            category_id=solution["category_id"]
        ))

    cur.close()
    conn.close()
    return render_template("edit_solutions.html", solution=solution)



# ลบ Solution
@app.route("/solutions/delete/<int:id>", methods=["POST"])
def delete_solutions(id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT category_id FROM solutions WHERE id=%s", (id,))
    solution = cur.fetchone()

    if solution:
        category_id = solution['category_id']
        cur.execute("DELETE FROM solutions WHERE id=%s", (id,))
        conn.commit()

    conn.close()
    flash("ลบวิธีแก้ปัญหาสำเร็จ", "success")
    return redirect(url_for("solutions", category_id=category_id))


@app.route("/solutions/<int:category_id>")
def solutions(category_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM solutions_categories_all WHERE id=%s", (category_id,))
    category = cur.fetchone()

    cur.execute("SELECT * FROM solutions WHERE category_id=%s ORDER BY id DESC", (category_id,))
    solutions = cur.fetchall()

    conn.close()
    return render_template("solutions.html", category=category, solutions=solutions)
    

@app.route("/solutions_categories_all")
def solutions_categories_all():
    conn = get_db_connection()
    cur = conn.cursor()

    # ดึงหมวดหมู่ทั้งหมด พร้อมนับจำนวนวิธีแก้ปัญหาในแต่ละหมวด
    cur.execute("""
        SELECT sc.id, sc.name, COUNT(s.id) AS problem_count
        FROM solutions_categories_all sc
        LEFT JOIN solutions s ON sc.id = s.category_id
        GROUP BY sc.id, sc.name
        ORDER BY sc.id DESC
    """)
    categories = cur.fetchall()
    conn.close()

    return render_template("solutions_categories_all.html", categories=categories)


@app.route("/add_category", methods=["GET", "POST"])
def add_category():
    if request.method == "POST":
        name = request.form.get("name")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO solutions_categories_all (name) VALUES (%s)", (name,))
        conn.commit()
        conn.close()
        flash("✅ เพิ่มหมวดหมู่สำเร็จ", "success")
        return redirect(url_for("solutions_categories_all"))


    return render_template("add_category.html")

@app.route("/delete_category/<int:id>", methods=["POST"])
def delete_category(id):
    conn = get_db_connection()
    cur = conn.cursor()

    # ถ้าตาราง solutions มี FOREIGN KEY category_id แบบ ON DELETE CASCADE
    # การลบ category จะลบ solution ที่อยู่ในหมวดนี้อัตโนมัติ
    try:
        cur.execute("DELETE FROM solutions_categories_all WHERE id=%s", (id,))
        conn.commit()
        flash("ลบหมวดหมู่เรียบร้อยแล้ว", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {e}", "danger")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("solutions_categories_all"))




# ---------------------------------
# RUN
# --------------------------------

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=True)
