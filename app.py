from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date, datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DATABASE = "attendance.db"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'faculty'
    );

    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        year INTEGER NOT NULL,
        email TEXT
    );

    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        attendance_date TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
        marked_at TEXT NOT NULL,
        UNIQUE(student_id, attendance_date),
        FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)
    if not db.execute("SELECT 1 FROM users WHERE username = ?", ("admin",)).fetchone():
        db.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            ("admin", generate_password_hash("admin123"), "admin")
        )
    db.commit()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = get_db().execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    total_students = db.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
    today = date.today().isoformat()
    present_today = db.execute(
        "SELECT COUNT(*) c FROM attendance WHERE attendance_date=? AND status='Present'",
        (today,)
    ).fetchone()["c"]
    total_records = db.execute("SELECT COUNT(*) c FROM attendance").fetchone()["c"]
    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_today=present_today,
        total_records=total_records,
        today=today
    )

@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    db = get_db()
    if request.method == "POST":
        try:
            db.execute("""
                INSERT INTO students(roll_no,name,department,year,email)
                VALUES(?,?,?,?,?)
            """, (
                request.form["roll_no"].strip(),
                request.form["name"].strip(),
                request.form["department"].strip(),
                int(request.form["year"]),
                request.form.get("email", "").strip()
            ))
            db.commit()
            flash("Student added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("Roll number already exists.", "danger")
        return redirect(url_for("students"))

    rows = db.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    return render_template("students.html", students=rows)

@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    db = get_db()
    selected_date = request.form.get("attendance_date") or request.args.get("attendance_date") or date.today().isoformat()

    if request.method == "POST":
        student_id = request.form["student_id"]
        status = request.form["status"]
        try:
            db.execute("""
                INSERT INTO attendance(student_id,attendance_date,status,marked_at)
                VALUES(?,?,?,?)
            """, (student_id, selected_date, status, datetime.now().isoformat(timespec="seconds")))
            db.commit()
            flash("Attendance marked.", "success")
        except sqlite3.IntegrityError:
            flash("Attendance already marked for this student on this date.", "danger")
        return redirect(url_for("attendance", attendance_date=selected_date))

    students = db.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    records = db.execute("""
        SELECT a.*, s.roll_no, s.name
        FROM attendance a
        JOIN students s ON s.id=a.student_id
        WHERE a.attendance_date=?
        ORDER BY s.roll_no
    """, (selected_date,)).fetchall()

    marked = {r["student_id"] for r in records}
    return render_template(
        "attendance.html",
        students=students,
        records=records,
        marked=marked,
        selected_date=selected_date
    )

@app.route("/reports")
@login_required
def reports():
    db = get_db()
    rows = db.execute("""
        SELECT s.id, s.roll_no, s.name, s.department,
               SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present,
               COUNT(a.id) AS total,
               CASE WHEN COUNT(a.id)=0 THEN 0
                    ELSE ROUND(100.0 * SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) / COUNT(a.id), 2)
               END AS percentage
        FROM students s
        LEFT JOIN attendance a ON a.student_id=s.id
        GROUP BY s.id
        ORDER BY s.roll_no
    """).fetchall()
    return render_template("reports.html", reports=rows)

@app.route("/student/<int:student_id>")
@login_required
def student_detail(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        return "Student not found", 404
    records = db.execute("""
        SELECT * FROM attendance
        WHERE student_id=?
        ORDER BY attendance_date DESC
    """, (student_id,)).fetchall()
    return render_template("student_detail.html", student=student, records=records)

@app.context_processor
def inject_now():
    return {"current_year": datetime.now().year}

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
