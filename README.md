# NEXTOUCH

NEXTOUCH is a local NFC necklace prototype for claim, edit, and public profile flows.

## Local routes

- `/tap/<id>`: public page opened after tapping a necklace
- `/account`: login, claim, and device management entry
- `/u/<slug>`: public profile preview route

## Run locally

```powershell
py .\server.py
```

Then open:

```text
http://127.0.0.1:4173/
```

## Structure

- `server.py`: Python standard library HTTP server + SQLite
- `index.html`: single-page app shell
- `app.js`: routing, auth, claim, and edit logic
- `styles.css`: NEXTOUCH black marble visual system

## Railway data persistence

- If you deploy on Railway, mount a persistent Volume at `/data`.
- The app will automatically use `/data/tap_necklace.sqlite3` on Railway when that mount exists.
- You can still override the database file manually with `DATABASE_PATH`.

## Backend API

- `GET /api/health`: check service, database path, and record counts.
- `GET /api/tap/<id>`: resolve one NFC entry. New IDs are created as unclaimed devices.
- `POST /api/register`: create an account and optionally claim one device.
- `POST /api/login`: sign in and optionally claim one unclaimed device.
- `PUT /api/profile`: update the current user's selected device profile.

### Admin batch devices

Set `ADMIN_API_TOKEN` in production before using admin APIs.

```powershell
$headers = @{ "X-Admin-Token" = "your-admin-token" }
$body = @{ count = 20; prefix = "NX"; size = 8 } | ConvertTo-Json
Invoke-RestMethod https://taptap.xin/api/admin/devices -Method POST -Headers $headers -ContentType "application/json" -Body $body
```

The response returns stable NFC URLs like `https://taptap.xin/tap/NXABC123`.

## Product direction

Each physical NFC tag should contain a stable URL such as:

```text
https://taptap.xin/tap/A8K2M7
```

Unclaimed tags show the claim page. Claimed tags show the owner public profile. Edits happen in the backend and do not require rewriting the tag.

<!-- railway deploy trigger: 2026-06-02 -->
