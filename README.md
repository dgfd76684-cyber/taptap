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

## Product direction

Each physical NFC tag should contain a stable URL such as:

```text
https://taptap.xin/tap/A8K2M7
```

Unclaimed tags show the claim page. Claimed tags show the owner public profile. Edits happen in the backend and do not require rewriting the tag.

<!-- railway deploy trigger: 2026-06-02 -->
