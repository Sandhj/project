#!/bin/bash

cd
apt update 
sudo apt install git

git clone https://github.com/Sandhj/project.git

cd project
python3 -m venv web
source web/bin/activate

pip install flask
pip install requests
pip install paramiko
deactivate

cd
cat <<EOL > /etc/systemd/system/app.service
[Unit]
Description=Run project script
After=network.target

[Service]
ExecStart=/bin/bash /root/project/run.sh
WorkingDirectory=/root/project
User=root
Group=root
Restart=always
StandardOutput=journal
StandardError=journal
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd dan aktifkan service
systemctl daemon-reload
systemctl enable app.service

# Menjalankan service
systemctl start app.service


cat <<EOL > /root/project/backup.py
import os
import shutil
import zipfile
import requests

# Konfigurasi
project_dir = "/root/project/"
backup_dir = os.path.join(project_dir, "backup")
files_to_backup = ["database.db", "list_xl.json", "server.json"]
zip_filename = "backup.zip"
telegram_token = "7360190308:AAH79nXyUiU4TRscBtYRLg14WVNfi1q1T1M"
chat_id = "576495165"

# Membuat folder backup jika belum ada
if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)

# Memindahkan file ke folder backup
for file in files_to_backup:
    src = os.path.join(project_dir, file)
    dest = os.path.join(backup_dir, file)
    if os.path.exists(src):
        shutil.copy2(src, dest)
    else:
        print(f"File {file} tidak ditemukan di {project_dir}")

# Membuat zip dari folder backup
zip_path = os.path.join(project_dir, zip_filename)
with zipfile.ZipFile(zip_path, 'w') as zipf:
    for root, _, files in os.walk(backup_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, backup_dir)
            zipf.write(file_path, arcname)

# Mengirim file ke bot Telegram
def send_to_telegram(file_path):
    url = f"https://api.telegram.org/bot{telegram_token}/sendDocument"
    with open(file_path, 'rb') as file:
        response = requests.post(
            url, 
            data={"chat_id": chat_id}, 
            files={"document": file}
        )
    if response.status_code == 200:
        print("Backup berhasil dikirim ke Telegram.")
    else:
        print(f"Error mengirim backup: {response.text}")

# Mengirim file zip
send_to_telegram(zip_path)
EOL

#pasang service backup

# Variabel
PROJECT_DIR="/root/project"
BACKUP_SCRIPT="$PROJECT_DIR/backup.py"
SERVICE_FILE="/etc/systemd/system/backup.service"
TIMER_FILE="/etc/systemd/system/backup.timer"

# Pastikan script backup.py ada
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo "File backup.py tidak ditemukan di $PROJECT_DIR"
    exit 1
fi

echo "Membuat systemd service dan timer untuk backup..."

# Membuat file service
cat <<EOF | sudo tee $SERVICE_FILE > /dev/null
[Unit]
Description=Backup Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $BACKUP_SCRIPT
WorkingDirectory=$PROJECT_DIR
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Membuat file timer
cat <<EOF | sudo tee $TIMER_FILE > /dev/null
[Unit]
Description=Run Backup Service Every 3 Hours

[Timer]
OnBootSec=5min
OnUnitActiveSec=3h
Unit=backup.service

[Install]
WantedBy=timers.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Mengaktifkan dan memulai timer
sudo systemctl enable backup.timer
sudo systemctl start backup.timer

echo "Setup selesai. Backup akan berjalan setiap 3 jam."

# Restore
cat <<EOL > /root/project/restore.py
import os
import zipfile
import requests

# Konfigurasi
project_dir = "/root/project/"
backup_file = os.path.join(project_dir, "backup.zip")
telegram_token = "7360190308:AAH79nXyUiU4TRscBtYRLg14WVNfi1q1T1M"
chat_id = "576495165"

# Fungsi untuk mendownload file dari bot Telegram
def download_backup():
    print("Menunggu file backup.zip...")
    url = f"https://api.telegram.org/bot{telegram_token}/getUpdates"
    response = requests.get(url)
    
    if response.status_code == 200:
        updates = response.json()
        # Cari pesan terakhir dengan file
        for update in reversed(updates.get("result", [])):
            if "document" in update.get("message", {}):
                document = update["message"]["document"]
                file_id = document["file_id"]
                file_name = document["file_name"]
                if file_name == "backup.zip":
                    print("File backup.zip ditemukan.")
                    # Dapatkan URL untuk mendownload file
                    file_url = f"https://api.telegram.org/bot{telegram_token}/getFile?file_id={file_id}"
                    file_path = requests.get(file_url).json()["result"]["file_path"]
                    download_url = f"https://api.telegram.org/file/bot{telegram_token}/{file_path}"
                    
                    # Download file
                    response = requests.get(download_url, stream=True)
                    if response.status_code == 200:
                        with open(backup_file, "wb") as f:
                            f.write(response.content)
                        print("File backup.zip berhasil didownload.")
                        return True
                    else:
                        print("Gagal mendownload file backup.zip.")
                        return False
    else:
        print("Gagal mendapatkan pembaruan dari Telegram.")
        return False

# Fungsi untuk mengekstrak file backup
def restore_backup():
    if os.path.exists(backup_file):
        print("Mengekstrak file backup.zip...")
        with zipfile.ZipFile(backup_file, "r") as zipf:
            zipf.extractall(project_dir)
        print("Restore selesai. File telah dikembalikan ke direktori:")
        print(f"- {project_dir}")
    else:
        print("File backup.zip tidak ditemukan.")

# Proses restore
if download_backup():
    restore_backup()
else:
    print("Proses restore gagal.")

EOL

cd
rm -r setup.sh

