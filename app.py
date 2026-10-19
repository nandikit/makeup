import os, sqlite3, uuid
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
# Vercel's deployment filesystem is read-only. /tmp is writable but ephemeral;
# use a managed database and object storage for persistent production data.
if os.environ.get("VERCEL"):
    DATA_DIR = Path("/tmp/makeup_by_kavyanandeesh")
else:
    DATA_DIR = ROOT
UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "site.db"
ALLOWED = {"jpg", "jpeg", "png", "webp", "gif"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-publishing")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS admins(
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS services(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Makeup',
            description TEXT NOT NULL DEFAULT '', price INTEGER NOT NULL DEFAULT 0)""")
        con.execute("""CREATE TABLE IF NOT EXISTS gallery(
            id INTEGER PRIMARY KEY AUTOINCREMENT, caption TEXT NOT NULL, filename TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        con.execute("""CREATE TABLE IF NOT EXISTS bookings(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL,
            service TEXT NOT NULL, event_date TEXT NOT NULL, message TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        if con.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
            username = os.environ.get("ADMIN_USERNAME", "admin")
            password = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
            con.execute("INSERT INTO admins(username,password_hash) VALUES(?,?)",
                        (username, generate_password_hash(password)))
        if con.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
            con.executemany("INSERT INTO services(name,category,description,price) VALUES(?,?,?,?)", [
                ("Bridal Signature", "Bridal", "A timeless bridal look with makeup, hair styling and finishing touches.", 0),
                ("Engagement Glow", "Engagement", "Soft glam for your engagement and special celebrations.", 0),
                ("Reception Glam", "Reception", "Elegant, camera-ready styling for your reception.", 0),
                ("Party Makeup", "Party", "A polished look for parties, functions and events.", 0),
                ("HD Makeup", "HD Makeup", "High-definition makeup designed for photos and video.", 0),
                ("Saree Draping & Hair", "Styling", "Beautiful draping and hairstyle finishing service.", 0),
            ])
init_db()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    # Uploads are served by Flask; on Vercel they are temporary until external
    # object storage is configured.
    return send_from_directory(UPLOADS, filename)

@app.get("/admin-login")
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("dashboard"))
    return render_template("admin.html", page="login")

@app.post("/admin-login")
def admin_login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    with connect() as con:
        row = con.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        session.clear()
        session["admin_id"] = row["id"]
        session["admin_username"] = row["username"]
        return redirect(url_for("dashboard"))
    flash("Username or password is incorrect.")
    return redirect(url_for("admin_login"))

@app.get("/admin")
@admin_required
def dashboard():
    with connect() as con:
        services = con.execute("SELECT * FROM services ORDER BY id DESC").fetchall()
        gallery = con.execute("SELECT * FROM gallery ORDER BY id DESC").fetchall()
        bookings = con.execute("SELECT * FROM bookings ORDER BY id DESC").fetchall()
    return render_template("admin.html", page="dashboard", username=session.get("admin_username"),
                           services=services, gallery=gallery, bookings=bookings)

@app.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.post("/admin/services/add")
@admin_required
def service_add():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "Makeup").strip() or "Makeup"
    description = request.form.get("description", "").strip()
    try:
        price = int(request.form.get("price", "0"))
        if price < 0: raise ValueError()
    except ValueError:
        flash("Enter a valid price (zero means Contact for price).")
        return redirect(url_for("dashboard"))
    if not name:
        flash("Service name is required.")
        return redirect(url_for("dashboard"))
    with connect() as con:
        con.execute("INSERT INTO services(name,category,description,price) VALUES(?,?,?,?)",
                    (name, category, description, price))
    flash("Service added to the website.")
    return redirect(url_for("dashboard"))

@app.post("/admin/services/<int:sid>/edit")
@admin_required
def service_edit(sid):
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "Makeup").strip() or "Makeup"
    description = request.form.get("description", "").strip()
    try:
        price = int(request.form.get("price", "0"))
        if not name or price < 0: raise ValueError()
    except ValueError:
        flash("Enter a service name and a valid price.")
        return redirect(url_for("dashboard"))
    with connect() as con:
        con.execute("UPDATE services SET name=?,category=?,description=?,price=? WHERE id=?",
                    (name, category, description, price, sid))
    flash("Service updated.")
    return redirect(url_for("dashboard"))

@app.post("/admin/services/<int:sid>/delete")
@admin_required
def service_delete(sid):
    with connect() as con:
        con.execute("DELETE FROM services WHERE id=?", (sid,))
    flash("Service deleted.")
    return redirect(url_for("dashboard"))

@app.post("/admin/gallery/add")
@admin_required
def gallery_add():
    f = request.files.get("photo")
    caption = request.form.get("caption", "").strip() or "Makeover look"
    if not f or not f.filename:
        flash("Choose a photo first.")
        return redirect(url_for("dashboard"))
    safe = secure_filename(f.filename)
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    if ext not in ALLOWED:
        flash("Upload JPG, JPEG, PNG, WEBP or GIF images.")
        return redirect(url_for("dashboard"))
    filename = uuid.uuid4().hex + "_" + safe
    f.save(UPLOADS / filename)
    with connect() as con:
        con.execute("INSERT INTO gallery(caption,filename) VALUES(?,?)", (caption, filename))
    flash("Photo added to the public gallery.")
    return redirect(url_for("dashboard"))

@app.post("/admin/gallery/<int:pid>/delete")
@admin_required
def gallery_delete(pid):
    with connect() as con:
        row = con.execute("SELECT filename FROM gallery WHERE id=?", (pid,)).fetchone()
        if row:
            try: (UPLOADS / row["filename"]).unlink(missing_ok=True)
            except OSError: pass
            con.execute("DELETE FROM gallery WHERE id=?", (pid,))
    flash("Gallery photo deleted.")
    return redirect(url_for("dashboard"))

@app.post("/api/bookings")
def booking_add():
    d = request.get_json(silent=True) or {}
    name, phone = str(d.get("name","")).strip(), str(d.get("phone","")).strip()
    service, event_date = str(d.get("service","")).strip(), str(d.get("event_date","")).strip()
    message = str(d.get("message","")).strip()
    if not all([name, phone, service, event_date]):
        return jsonify(error="Please complete name, phone, service and event date."), 400
    with connect() as con:
        con.execute("INSERT INTO bookings(name,phone,service,event_date,message) VALUES(?,?,?,?,?)",
                    (name, phone, service, event_date, message))
    return jsonify(ok=True), 201

@app.get("/api/public")
def public_data():
    with connect() as con:
        services = con.execute("SELECT id,name,category,description,price FROM services ORDER BY id").fetchall()
        gallery = con.execute("SELECT id,caption,filename FROM gallery ORDER BY id DESC").fetchall()
    return jsonify(services=[dict(r) for r in services],
                   gallery=[{"id":r["id"],"caption":r["caption"],
                             "url":url_for("uploaded_file", filename=r["filename"])} for r in gallery])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
