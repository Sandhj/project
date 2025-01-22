from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Database setup
def init_db():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                balance REAL DEFAULT 0.0
            )
        """)
        conn.commit()

# Home route
@app.route("/")
def home():
    if "username" in session:
        username = session["username"]
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE username = ?", (username,))
            balance = cursor.fetchone()[0]
        return render_template("dashboard.html", username=username, balance=balance)
    return redirect(url_for("login"))

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
        if user:
            session["username"] = username
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")

# Register route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                flash("Registration successful. Please login.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username already exists. Try a different one.", "danger")
    return render_template("register.html")

# Add balance route
@app.route("/add_balance", methods=["GET", "POST"])
def add_balance():
    if "username" not in session:
        flash("You need to log in first.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form["username"]
        balance_to_add = request.form["balance"]

        if not balance_to_add.isdigit() or int(balance_to_add) <= 0:
            flash("Invalid balance amount. Please enter a positive number.", "danger")
            return render_template("add_balance.html")

        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            if user:
                new_balance = user[3] + float(balance_to_add)  # user[3] is the current balance
                cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, username))
                conn.commit()
                flash(f"Successfully added ${balance_to_add} to {username}'s account.", "success")
            else:
                flash("User not found. Please check the username.", "danger")

    return render_template("add_balance.html")

# Logout route
@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5003)
