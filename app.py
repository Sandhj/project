from flask import Flask, render_template, request, redirect, session, g, flash, url_for, jsonify, flash
import sqlite3
import os
import paramiko
import subprocess
import json
import shutil
import json
import urllib.parse

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
def login_temp():
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

# -------------------create account premium ----------------

# Fungsi untuk mendapatkan jumlah pengguna (current) melalui SSH
def get_current_users_vpn(hostname, username, password):
    try:
        # Setup SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Menerima host key yang tidak dikenal
        
        # Connect to the server
        ssh.connect(hostname, username=username, password=password)

        # Jalankan script user.sh dan ambil outputnya
        stdin, stdout, stderr = ssh.exec_command("/root/user.sh")
        output = stdout.read().decode().strip()  # Ambil hasil output
        
        ssh.close()
        
        # Kembalikan jumlah user yang sedang aktif (current) sebagai integer
        return int(output)
    except Exception as e:
        print(f"Error: {e}")
        return None  # Jika gagal, kembalikan None
# Fungsi untuk mendapatkan daftar VPS dari file server.json
def get_vps_list():
    with open('server.json', 'r') as f:
        return json.load(f)

@app.route('/vps-list', methods=['GET'])
def vps_list():
    # Membaca daftar VPS dari file JSON
    vps_list = get_vps_list()
    
    # Set max_user
    max_user = 20
    
    filtered_vps = []
    
    # Memeriksa jumlah pengguna (current) pada masing-masing VPS
    for vps in vps_list:
        current_users = get_current_users_vpn(vps["hostname"], vps["username"], vps["password"])
        
        # Jika jumlah pengguna belum mencapai max_user, tambahkan ke daftar
        if current_users is not None and current_users < max_user:
            vps["current_users"] = current_users
            vps["max_user"] = max_user
            filtered_vps.append(vps)
    
    # Mengirimkan daftar VPS yang belum mencapai max_user
    return jsonify(filtered_vps)

# Fungsi untuk menghubungkan ke VPS dan menjalankan skrip
def run_script_on_vps(vps, protocol, username, expired):
    try:
        # Koneksi SSH ke VPS
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Menambahkan host key jika tidak ada
        ssh.connect(vps['hostname'], username=vps['username'], password=vps['password'])

        # Jalankan skrip di VPS
        command = f"/usr/bin/create_{protocol}"
        stdin, stdout, stderr = ssh.exec_command(command)
        stdin.write(f"{username}\n{expired}\n")
        stdin.flush()

        # Ambil output dari skrip
        output = stdout.read().decode('utf-8')

        ssh.close()
        
        return output

    except Exception as e:
        print(f"Error: {str(e)}")
        return f"Error: {str(e)}"

@app.route('/create_temp', methods=['GET'])
def create_account_temp():
    return render_template('create.html')

@app.route('/create', methods=['POST'])
def create_account():
    # Cek sesi aktif
    if 'username' not in session:
        return redirect('/login')

    # Ambil username dari sesi aktif
    active_user = session['username']

    # Ambil data dari form
    protocol = request.form['protocol']
    device = request.form['device']
    username = request.form['username']
    expired = int(request.form['expired'])
    vps_name = request.form['vps']  # Nama VPS yang dipilih dari dropdown

    # Logika pengurangan saldo
    cost_per_device = {'hp': 5000, 'stb': 10000}  # Biaya per device
    cost_per_expired = {30: 1, 60: 2, 90: 3, 120: 4}  # Faktor pengganda berdasarkan expired

    # Validasi device dan expired
    if device not in cost_per_device or expired not in cost_per_expired:
        return "Invalid device or expired value", 400

    # Hitung biaya pengurangan saldo
    total_cost = cost_per_device[device] * cost_per_expired[expired]

    # Cek saldo pengguna
    db = get_db()
    cursor = db.cursor()

    # Ambil saldo pengguna aktif
    cursor.execute("SELECT balance FROM users WHERE username = ?", (active_user,))
    user_data = cursor.fetchone()

    if not user_data:
        flash("Silahkan Login Kembali dan coba lagi", "error")
        return redirect('/create_temp')

    current_balance = user_data['balance']

    # Periksa apakah saldo mencukupi
    if current_balance < total_cost:
        flash("Saldo Kamu Tidak Mencukupi Untuk Melanjutkan Transaksi.", "error")
        return redirect('/create_temp')

    # Kurangi saldo
    new_balance = current_balance - total_cost
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, active_user))
    db.commit()

    # Ambil daftar VPS
    vps_list = get_vps_list()
    vps = next((v for v in vps_list if v['name'] == vps_name), None)

    if not vps:
        flash("VPS not found.", "error")
        return redirect('/create_temp')

    print(f"Received data - Protocol: {protocol}, Device: {device}, Username: {username}, Expired: {expired}, Cost: {total_cost}")

    # Menjalankan skrip shell di VPS yang dipilih
    output = run_script_on_vps(vps, protocol, username, expired)

    return render_template(
        'result.html',
        username=username,
        device=device,
        expired=expired,
        protocol=protocol,
        output=output,
        cost=total_cost,
        balance=new_balance
    )


@app.route('/result')
def result():
    # Ambil data yang diterima dari URL dan tampilkan di result.html
    device = request.args.get('device')
    username = request.args.get('username')
    expired = request.args.get('expired')
    protocol = request.args.get('protocol')
    output = request.args.get('output')

    return render_template(
        'result.html',
        username=username,
        expired=expired,
        protocol=protocol,
        device=device,
        output=output,
    )

#------------- add & delete server -----------

# Lokasi file server.json
SERVER_FILE = "/root/project/server.json"

def load_servers():
    """Load servers from the JSON file."""
    if os.path.exists(SERVER_FILE):
        with open(SERVER_FILE, "r") as file:
            return json.load(file)
    return []

def save_servers(servers):
    """Save servers to the JSON file."""
    with open(SERVER_FILE, "w") as file:
        json.dump(servers, file, indent=4)

@app.route('/add_server_temp')
def add_server_temp():
    """Halaman Form untuk menambah server."""
    return render_template('add_server.html')

@app.route('/add_server', methods=['POST'])
def add_server():
    try:
        # Ambil data dari form
        name = request.form['name']
        hostname = request.form['hostname']
        username = request.form['username']
        password = request.form['password']

        # Validasi input (contoh: semua field harus diisi)
        if not all([name, hostname, username, password]):
            flash("Semua field harus diisi!", "error")
            return redirect(url_for('home'))

        # Buat data server baru
        new_server = {
            "name": name,
            "hostname": hostname,
            "username": username,
            "password": password
        }

        # Load server list dan tambahkan server baru
        servers = load_servers()
        servers.append(new_server)
        save_servers(servers)

        flash("Server berhasil ditambahkan!", "success")
        return redirect(url_for('add_server_temp'))

    except Exception as e:
        flash(f"Terjadi kesalahan: {e}", "error")
        return redirect(url_for('add_server_temp'))

@app.route('/delete_server', methods=['GET', 'POST'])
def delete_server():
    if request.method == 'GET':
        # Menampilkan daftar server
        servers = load_servers()
        return render_template('delete_server.html', servers=servers)

    elif request.method == 'POST':
        # Menghapus server berdasarkan nama
        name_to_delete = request.form['name']
        servers = load_servers()
        updated_servers = [server for server in servers if server['name'] != name_to_delete]

        if len(servers) == len(updated_servers):
            flash(f"Server dengan nama '{name_to_delete}' tidak ditemukan!", "error")
        else:
            save_servers(updated_servers)
            flash(f"Server '{name_to_delete}' berhasil dihapus!", "success")
        
        return redirect(url_for('delete_server'))

#------------------- Fungsi Dor XL --------------
# Path ke file list_xl.json
DATA_FILE = '/root/project/list_xl.json'

# Endpoint untuk halaman utama
@app.route('/list_xl')
def list_xl():
    return render_template('list_xl.html')

# Endpoint untuk mendapatkan daftar paket
@app.route('/get_packages', methods=['GET'])
def get_packages():
    try:
        with open(DATA_FILE, 'r') as file:
            data = json.load(file)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#----------------------------------

# Path ke file list_xl.json dan backup
DATA_FILE = '/root/project/list_xl.json'

# Endpoint untuk halaman utama
@app.route('/add_list_xl')
def add_list_xl():
    return render_template('add_list_xl.html')

# Endpoint untuk menambahkan paket
@app.route('/add_package', methods=['POST'])
def add_package():
    try:
        new_package = request.json
        with open(DATA_FILE, 'r') as file:
            data = json.load(file)

        data[new_package['name']] = new_package['detail']

        with open(DATA_FILE, 'w') as file:
            json.dump(data, file, indent=4)

        return jsonify({"message": "Paket berhasil ditambahkan!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint untuk memperbarui paket
@app.route('/update_package/<package_name>', methods=['PUT'])
def update_package(package_name):
    try:
        updated_package = request.json
        with open(DATA_FILE, 'r') as file:
            data = json.load(file)

        if package_name in data:
            data[updated_package['name']] = updated_package['detail']
            if package_name != updated_package['name']:
                del data[package_name]  # Hapus nama lama jika diperbarui

            with open(DATA_FILE, 'w') as file:
                json.dump(data, file, indent=4)

            return jsonify({"message": "Paket berhasil diperbarui!"}), 200
        else:
            return jsonify({"error": "Paket tidak ditemukan!"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint untuk menghapus paket
@app.route('/delete_package/<package_name>', methods=['DELETE'])
def delete_package(package_name):
    try:
        with open(DATA_FILE, 'r') as file:
            data = json.load(file)

        if package_name in data:
            del data[package_name]
            with open(DATA_FILE, 'w') as file:
                json.dump(data, file, indent=4)

            return jsonify({"message": "Paket berhasil dihapus!"}), 200
        else:
            return jsonify({"error": "Paket tidak ditemukan!"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#-------------- Saldo add -------------
# Route untuk form tambah saldo
@app.route("/add_balance", methods=["GET", "POST"])
def add_balance():
    if request.method == "POST":
        username = request.form.get("username")
        balance_to_add = request.form.get("balance")

        if not username or not balance_to_add:
            flash("Username dan jumlah saldo harus diisi.", "error")
            return redirect("/add_balance")

        try:
            balance_to_add = int(balance_to_add)
            if balance_to_add <= 0:
                flash("Jumlah saldo harus lebih dari 0.", "error")
                return redirect("/add_balance")
        except ValueError:
            flash("Jumlah saldo harus berupa angka.", "error")
            return redirect("/add_balance")

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user:
            new_balance = user["balance"] + balance_to_add
            cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, username))
            db.commit()
            flash(f"Saldo berhasil ditambahkan untuk {username}. Saldo baru: {new_balance}", "success")
        else:
            flash(f"Pengguna dengan username '{username}' tidak ditemukan.", "error")

        return redirect("/add_balance")

    return render_template("add_balance.html")

#------------- Home Template -----------
#Fungsi untuk memeriksa status VPS (ping)
def check_vps_status(hostname):
    try:
        # Perintah ping ke setiap VPS
        result = subprocess.run(
            ["ping", "-c", "1", hostname],  # Ganti dengan IP/hostname VPS
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            # Ambil latensi dari hasil ping
            for line in result.stdout.split("\n"):
                if "time=" in line:
                    latency = line.split("time=")[1].split(" ")[0]
                    # Ubah latensi ke milidetik (ms)
                    latency_ms = int(float(latency) * 1000)
                    return {"status": "ON", "latency": f"{latency_ms} ms"}
        return {"status": "OFF", "latency": "-"}
    except Exception as e:
        return {"status": "OFF", "latency": "-"}

# Fungsi untuk mendapatkan jumlah pengguna (current) melalui SSH
def get_current_users(hostname, username, password):
    try:
        # Setup SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Menerima host key yang tidak dikenal
        
        # Connect to the server
        ssh.connect(hostname, username=username, password=password)

        # Jalankan script user.sh dan ambil outputnya
        stdin, stdout, stderr = ssh.exec_command("/root/user.sh")
        output = stdout.read().decode().strip()  # Ambil hasil output
        
        ssh.close()
        
        # Kembalikan jumlah user yang sedang aktif (current) sebagai integer
        return int(output)
    except Exception as e:
        print(f"Error: {e}")
        return None  # Jika gagal, kembalikan None

# Route untuk halaman utama
@app.route("/home")
def home():
    return render_template("home.html")

# Route untuk mendapatkan status VPS dan informasi lainnya
@app.route("/status", methods=["GET"])
def get_status():
    # Membaca data dari file JSON
    with open('server.json') as f:
        vps_list = json.load(f)
    
    # Set max_user
    max_user = 20

    # Memeriksa status masing-masing VPS
    for vps in vps_list:
        vps_status = check_vps_status(vps["hostname"])
        vps["status"] = vps_status["status"]
        vps["latency"] = vps_status["latency"]
        
        # Ambil current user menggunakan paramiko
        current_users = get_current_users(vps["hostname"], vps["username"], vps["password"])  # Pastikan menambahkan username dan password di server.json
        vps["current_users"] = current_users if current_users is not None else 0
        vps["max_user"] = max_user
    
    return jsonify(vps_list)


# ---------------Fungsi Create FREE VPN Account-----------

@app.route('/vpn_free_temp', methods=['GET', 'POST'])
def vpn_free_temp():
    return render_template('vpn_free.html')

@app.route('/vpn_free', methods=['POST'])
def vpn_free():
    if request.method == 'POST':
        # Ambil data dari form
        protocol = request.form['protocol']
        device = request.form['device']
        username = request.form['username']
        expired = request.form['expired']

        # Debugging: Log data yang diterima dari form
        print(f"Received data - Protocol: {protocol}, Device: {device}, Username: {username}, Expired: {expired}")

        # Konfigurasi koneksi ke VPS lain
        remote_host = "178.128.86.18"
        remote_port = 22
        remote_user = "root"
        remote_password = "@1Vpsbysan"

        try:
            # Membuat koneksi SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=remote_host, port=remote_port, username=remote_user, password=remote_password)

            # Menjalankan perintah di VPS lain
            command = f"echo -e '{username}\n{expired}' | /usr/bin/create_{protocol}"
            stdin, stdout, stderr = ssh.exec_command(command)

            # Membaca output dan error dari perintah yang dijalankan
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            # Debugging: Log output dan error
            print(f"Output: {output}")
            print(f"Error: {error}")

            ssh.close()

            # Jika ada error, tampilkan di hasil render
            if error:
                return render_template(
                    'result.html',
                    username=username,
                    device=device,
                    expired=expired,
                    protocol=protocol,
                    output=f"Error: {error}"
                )

            # Jika berhasil, kirim output ke template
            return render_template(
                'result.html',
                username=username,
                device=device,
                expired=expired,
                protocol=protocol,
                output=output
            )
        except Exception as e:
            # Jika terjadi error dalam koneksi SSH
            print(f"SSH connection error: {str(e)}")
            return render_template(
                'result.html',
                username=username,
                device=device,
                expired=expired,
                protocol=protocol,
                output=f"SSH connection error: {str(e)}"
            )

#--------------- Fungsi Deposit -----------
# Route utama untuk menampilkan form HTML
@app.route('/deposit', methods=['GET'])
def deposit():
    return render_template('deposit.html')  # Pastikan file HTML disimpan di folder "templates"

# Route untuk memproses data dari form
@app.route('/process', methods=['POST'])
def process_form():
    username = request.form.get('username')
    deposit_amount = request.form.get('depositAmount')

    if username and deposit_amount:
        # Format pesan untuk WhatsApp
        message = f"PERMINTAAN DEPOSIT\nUsername: {username}\nJumlah Deposit: {deposit_amount}"
        encoded_message = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/6285155208019?text={encoded_message}"

        return redirect(whatsapp_url)
    else:
        return jsonify({"error": "Harap isi semua data!"}), 400


@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Anda telah logout.", "info")
    return redirect("/login")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5003)
