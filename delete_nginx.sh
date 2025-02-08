#!/bin/bash

# Meminta user memasukkan domain yang ingin dihapus
read -p "Masukkan domain yang ingin dihapus (contoh: web.easyvpn.biz.id): " DOMAIN

# Konfirmasi sebelum menghapus
read -p "Apakah Anda yakin ingin menghapus domain $DOMAIN dan SSL-nya? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" ]]; then
    echo "Penghapusan dibatalkan."
    exit 1
fi

echo "Menghapus konfigurasi Nginx untuk $DOMAIN..."
# Hapus file konfigurasi dari sites-available dan sites-enabled
rm -f /etc/nginx/sites-available/$DOMAIN
rm -f /etc/nginx/sites-enabled/$DOMAIN
unlink /etc/nginx/sites-enabled/$DOMAIN 2>/dev/null

echo "Menghapus SSL dari Let's Encrypt..."
# Hapus sertifikat dari Certbot
certbot delete --cert-name $DOMAIN

# Pastikan semua file SSL dihapus
rm -rf /etc/letsencrypt/live/$DOMAIN
rm -rf /etc/letsencrypt/archive/$DOMAIN
rm -rf /etc/letsencrypt/renewal/$DOMAIN.conf

echo "Memeriksa konfigurasi Nginx..."
# Periksa apakah konfigurasi valid
nginx -t

# Jika konfigurasi valid, restart Nginx
if [[ $? -eq 0 ]]; then
    echo "Restarting Nginx..."
    systemctl restart nginx
    echo "Domain $DOMAIN dan SSL telah berhasil dihapus!"
else
    echo "Kesalahan pada konfigurasi Nginx. Periksa secara manual!"
fi
