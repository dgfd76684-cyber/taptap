#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/nextouch}"
APP_USER="${APP_USER:-nextouch}"
DOMAIN="${DOMAIN:-taptap.xin}"
PORT="${PORT:-4173}"
DB_PATH="${DATABASE_PATH:-/var/lib/nextouch/tap_necklace.sqlite3}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root."
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx unzip rsync

id -u "${APP_USER}" >/dev/null 2>&1 || useradd --system --home "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
mkdir -p "${APP_DIR}" "$(dirname "${DB_PATH}")"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" "$(dirname "${DB_PATH}")"

cat >/etc/systemd/system/nextouch.service <<SERVICE
[Unit]
Description=NEXTOUCH NFC social profile
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=HOST=127.0.0.1
Environment=PORT=${PORT}
Environment=DATABASE_PATH=${DB_PATH}
Environment=ADMIN_API_TOKEN=change-this-token
ExecStart=/usr/bin/python3 ${APP_DIR}/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

cat >/etc/nginx/sites-available/nextouch <<NGINX
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};

    client_max_body_size 8m;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/nextouch /etc/nginx/sites-enabled/nextouch
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload
systemctl enable nextouch
systemctl restart nginx

echo "Base server is ready."
echo "Upload project files to ${APP_DIR}, then run:"
echo "  systemctl restart nextouch"
echo "  certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
