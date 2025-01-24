from flask import Flask, render_template, request, redirect, session, g, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = "database.db"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# Initialize database
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                balance INTEGER DEFAULT 0
            )
        ''')
        db.commit()

@app.route("/")
def home():
    if "username" in session:
        if session["username"] == "mastersandi":
            return redirect("/admin")
        else:
            return redirect("/guest")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        if user:
            session["username"] = username
            if username == "mastersandi":
                return redirect("/admin")
            return redirect("/guest")
        else:
            flash("Username atau password salah!", "error")
            return redirect("/login")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            db.commit()
            flash("Registrasi berhasil! Silakan login.", "success")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("Username sudah digunakan!", "error")
            return redirect("/register")
    return render_template("register.html")

@app.route("/guest")
def guest_dashboard():
    if "username" not in session or session["username"] == "mastersandi":
        return redirect("/login")
    username = session["username"]
    db = get_db()
    user = db.execute("SELECT balance FROM users WHERE username = ?", (username,)).fetchone()
    balance = user["balance"] if user else 0
    return render_template("dash_guest.html", username=username, balance=balance)

@app.route("/admin")
def admin_dashboard():
    if "username" not in session or session["username"] != "mastersandi":
        return redirect("/login")
    username = session["username"]
    db = get_db()
    user = db.execute("SELECT balance FROM users WHERE username = ?", (username,)).fetchone()
    balance = user["balance"] if user else 0
    return render_template("dash_admin.html", username=username, balance=balance)

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Anda telah logout.", "info")
    return redirect("/login")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
