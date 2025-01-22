from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import subprocess

app = Flask(__name__)
app.secret_key = os.urandom(24)

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

@app.route("/index_guest")
def index_guest():
    return render_template("index.html")

# Home route
@app.route("/dashboard")
def dashboard():
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
            return redirect(url_for("index_guest"))
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

# ---------------Fungsi Create Account------------
@app.route('/create_temp')
def create_temp():
    return render_template("create.html")
    
@app.route('/create', methods=['POST'])
def create_account():
    if request.method == 'POST':
        # Ambil data dari form
        protocol = request.form['protocol']
        device = request.form['device']
        username = request.form['username']
        expired = request.form['expired']

        # Pastikan ada sesi login
        if 'username' not in session:
            flash("You need to be logged in to create a VPN account.", "danger")
            return redirect(url_for("login"))

        logged_in_user = session["username"]

        # Ambil data pengguna dari database berdasarkan sesi login
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE username = ?", (logged_in_user,))
            user_data = cursor.fetchone()
            
            if not user_data:
                flash("User not found in database.", "danger")
                return redirect(url_for("login"))

            balance = user_data[0]

        # Tentukan biaya pembuatan akun VPN berdasarkan nilai dari protocol
        if protocol == "stb":
            vpn_creation_cost = 8000
        elif protocol == "hp":
            vpn_creation_cost = 4000
        else:
            vpn_creation_cost = 8000  # Anda bisa menambahkan biaya default jika diperlukan

        # Pastikan saldo cukup
        if balance < vpn_creation_cost:
            flash("Saldo anda tidak mencukupi untuk transaksi ini.", "danger")
            return redirect(url_for("create_temp"))

        # Kurangi saldo pengguna
        new_balance = balance - vpn_creation_cost

        # Update saldo di database
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, logged_in_user))
            conn.commit()

        # Debugging: Log data yang diterima dari form
        print(f"Received data - Protocol: {protocol}, Device: {device}, Username: {username}, Expired: {expired}")

        # Menjalankan skrip shell dengan input dari user
        try:
            # Debugging: Log sebelum menjalankan skrip shell
            print(f"Running script for protocol: {protocol} with username: {username} and expired: {expired}")

            # Menjalankan skrip shell dengan memberikan input interaktif (username dan expired)
            result = subprocess.run(
                [f"/usr/bin/create_{protocol}"],  # Skrip untuk protokol (vmess, vless, trojan)
                input=f"{username}\n{expired}\n",  # Memberikan input username dan expired
                text=True,
                capture_output=True,
                check=True
            )
            
            # Jika berhasil, outputnya akan ditangkap oleh result.stdout
            print(f"Script output: {result.stdout.strip()}")

        except subprocess.CalledProcessError as e:
            # Tangkap kesalahan jika terjadi error pada eksekusi skrip shell
            print(f"Error: {e.stderr.strip()}")
            output = f"Error: {e.stderr.strip()}"
            return render_template(
                'result.html',
                username=username,
                expired=expired,
                protocol=protocol,
                output=output
            )

        # Membaca file output yang dihasilkan oleh skrip shell
        output_file = f"/root/project/{username}_output.txt"
        if os.path.exists(output_file):
            with open(output_file, 'r') as file:
                output = file.read()

            # Menghapus file output setelah dibaca
            os.remove(output_file)

        # Mengalihkan ke halaman result
        return redirect(url_for('result', username=username, expired=expired, output=output))

@app.route('/result')
def result():
    # Ambil data yang diterima dari URL dan tampilkan di result.html
    username = request.args.get('username')
    expired = request.args.get('expired')
    output = request.args.get('output')

    # Kembalikan data ke halaman result.html tanpa WhatsApp link
    return render_template(
        'result.html',
        username=username,
        expired=expired,
        output=output
    )
    

# Logout route
@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5003)
