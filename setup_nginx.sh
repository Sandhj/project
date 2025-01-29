#install Nginx
sudo apt update
sudo apt install nginx -y
sudo apt update

cd /etc/nginx/sites-available/
wget -q https://raw.githubusercontent.com/Sandhj/project/main/web.easyvpn.biz.id
sudo ln -s /etc/nginx/sites-available/web.easyvpn.biz.id /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

#pasang SSL
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d web.easyvpn.biz.id

