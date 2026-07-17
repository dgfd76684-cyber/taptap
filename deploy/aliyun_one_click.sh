#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/nextouch}"
DATA_DIR="${DATA_DIR:-/var/lib/nextouch}"
REPO_URL="${REPO_URL:-https://github.com/dgfd76684-cyber/taptap.git}"
PORT="${PORT:-80}"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root, for example: curl -fsSL ... | sudo bash"
  exit 1
fi

echo "== NEXTOUCH Aliyun deploy =="
echo "App dir: ${APP_DIR}"
echo "Data dir: ${DATA_DIR}"
echo "Port: ${PORT}"

install_packages() {
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y git curl python3.11
  elif command -v yum >/dev/null 2>&1; then
    yum install -y git curl python3.11
  elif command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y git python3 curl
  else
    echo "No supported package manager found."
    exit 1
  fi
}

install_packages

if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
  elif command -v python3.10 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.10)"
  elif command -v python3.9 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.9)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "No usable Python 3 interpreter found."
    exit 1
  fi
fi

echo "== Pull project =="
rm -rf /tmp/nextouch-src
git clone --depth 1 "${REPO_URL}" /tmp/nextouch-src

echo "== Install files =="
rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}" "${DATA_DIR}"
cp -a /tmp/nextouch-src/. "${APP_DIR}/"

echo "== Prepare persistent database =="
touch "${DATA_DIR}/tap_necklace.sqlite3"
chmod 664 "${DATA_DIR}/tap_necklace.sqlite3"

echo "== Create systemd service =="
cat >/etc/systemd/system/nextouch.service <<SERVICE
[Unit]
Description=NEXTOUCH NFC Social Profile
After=network.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment=HOST=0.0.0.0
Environment=PORT=${PORT}
Environment=DATABASE_PATH=${DATA_DIR}/tap_necklace.sqlite3
ExecStart=${PYTHON_BIN} ${APP_DIR}/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

if [[ "${PORT}" == "80" ]]; then
  echo "== Free port 80 if panel web server is occupying it =="
  systemctl stop nginx 2>/dev/null || true
  systemctl stop httpd 2>/dev/null || true
fi

echo "== Start service =="
systemctl daemon-reload
systemctl enable nextouch
systemctl restart nextouch

sleep 2
echo "== Status =="
systemctl --no-pager --full status nextouch || true
echo "== Local check =="
curl -I "http://127.0.0.1:${PORT}/" || true

echo "== Done =="
echo "Visit: http://47.97.252.7"
