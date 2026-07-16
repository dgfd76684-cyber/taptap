# NEXTOUCH Aliyun Deployment Notes

This project is a single Python HTTP service. It does not need Node.js.

## Recommended server

- Aliyun Lightweight Application Server
- Region: Hangzhou
- Image: Baota panel is OK for UI-first management, Ubuntu is cleaner for command-line deployment
- Open firewall/security group ports: 80, 443, and optionally 4173 for temporary testing

## Runtime

```bash
python3 server.py
```

Production environment:

```bash
HOST=127.0.0.1
PORT=4173
DATABASE_PATH=/var/lib/nextouch/tap_necklace.sqlite3
ADMIN_API_TOKEN=<set-a-long-random-token>
```

## Fast command-line deployment

1. Upload project files to `/opt/nextouch`.
2. Run:

```bash
sudo bash deploy/alicloud_setup.sh
sudo systemctl restart nextouch
```

3. Point DNS `taptap.xin` and `www.taptap.xin` to the server public IP.
4. Enable HTTPS:

```bash
sudo certbot --nginx -d taptap.xin -d www.taptap.xin
```

## Health check

```bash
curl http://127.0.0.1:4173/api/health
curl http://taptap.xin/api/health
```
