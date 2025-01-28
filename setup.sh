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


# Prompt untuk token bot Telegram dan chat ID
echo "Masukkan Token Telegram Anda (didapat dari BotFather): "
read Token_tele
echo "Masukkan Chat ID Telegram Anda (bisa menggunakan @userinfobot): "
read id_tele

# Tentukan direktori tempat script dan konfigurasi
BACKUP_DIR="/root/project/backups"
PROJECT_DIR="/root/project"

# Buat file backup_bot.py
cat > $PROJECT_DIR/backup_bot.py << EOF
import os
import zipfile
import schedule
import time
import telebot
from datetime import datetime

# Konfigurasi Token Bot Telegram
BOT_TOKEN = "$Token_tele"
CHAT_ID = "$id_tele"

# Direktori dan file yang akan di-backup
FILES_TO_BACKUP = [
    "/root/project/database.db",
    "/root/project/list_xl.json",
    "/root/project/server.json",
]
BACKUP_DIR = "/root/project/backups"
ZIP_FILENAME = os.path.join(BACKUP_DIR, "backup.zip")

# Inisialisasi Bot Telegram
bot = telebot.TeleBot(BOT_TOKEN)

# Membuat ZIP file dari daftar file
def create_zip():
    os.makedirs(BACKUP_DIR, exist_ok=True)  # Membuat direktori backup jika belum ada
    with zipfile.ZipFile(ZIP_FILENAME, "w") as backup_zip:
        for file in FILES_TO_BACKUP:
            if os.path.exists(file):
                backup_zip.write(file, os.path.basename(file))
            else:
                print(f"File tidak ditemukan: {file}")
    print(f"ZIP file berhasil dibuat: {ZIP_FILENAME}")

# Mengirim ZIP file ke Telegram
def send_backup_to_telegram():
    create_zip()
    with open(ZIP_FILENAME, "rb") as zip_file:
        bot.send_document(chat_id=CHAT_ID, document=zip_file, caption="Backup Otomatis")
    print("Backup berhasil dikirim ke Telegram.")

# Jadwal backup
SCHEDULE_TIMES = [1, 3, 6, 9, 12, 13, 18, 22]
for hour in SCHEDULE_TIMES:
    schedule.every().day.at(f"{hour:02}:00").do(send_backup_to_telegram)

# Looping jadwal
print("Menjalankan jadwal backup...")
while True:
    schedule.run_pending()
    time.sleep(1)
EOF

# Buat file restore_bot.py
cat > $PROJECT_DIR/restore_bot.py << EOF
import os
import telebot

# Konfigurasi Token Bot Telegram
BOT_TOKEN = "$Token_tele"

# Direktori backup
BACKUP_DIR = "/root/project/backups"
ZIP_FILENAME = os.path.join(BACKUP_DIR, "backup.zip")

# Inisialisasi Bot Telegram
bot = telebot.TeleBot(BOT_TOKEN)

# Command untuk restore file
@bot.message_handler(commands=["restore"])
def restore_backup(message):
    if os.path.exists(ZIP_FILENAME):
        with open(ZIP_FILENAME, "rb") as zip_file:
            bot.send_document(chat_id=message.chat.id, document=zip_file, caption="Berikut adalah file backup terakhir.")
    else:
        bot.reply_to(message, "File backup tidak ditemukan.")

# Menjalankan bot
print("Bot Telegram untuk restore sedang berjalan...")
bot.infinity_polling()
EOF

# Buat systemd service untuk backup bot
cat > /etc/systemd/system/backup_bot.service << EOF
[Unit]
Description=Backup Bot Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $PROJECT_DIR/backup_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Aktifkan dan mulai service backup bot
systemctl enable backup_bot.service
systemctl start backup_bot.service

# Menambahkan cron job untuk menjalankan backup bot pada reboot
(crontab -l ; echo "@reboot /usr/bin/python3 $PROJECT_DIR/backup_bot.py") | crontab -

# Selesai
echo "Setup selesai. Backup bot dan restore bot telah dikonfigurasi."
echo "Backup bot telah dijalankan dan akan berjalan otomatis setiap reboot."
echo "Untuk restore, jalankan bot restore dengan perintah: python3 $PROJECT_DIR/restore_bot.py"
