from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import secrets
import sqlite3
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "tap_necklace.sqlite3"
SESSION_COOKIE = "tap_session"
DEMO_QR = "/assets/wechat-friend-qr.jpg"


def db_path() -> Path:
    configured = os.environ.get("DATABASE_PATH")
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_DB_PATH


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                avatar TEXT NOT NULL DEFAULT '',
                bio TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                wechat TEXT NOT NULL DEFAULT '',
                wechat_qr TEXT NOT NULL DEFAULT '',
                douyin TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS device_profiles (
                token TEXT PRIMARY KEY REFERENCES necklaces(token) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                avatar TEXT NOT NULL DEFAULT '',
                bio TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                wechat TEXT NOT NULL DEFAULT '',
                wechat_qr TEXT NOT NULL DEFAULT '',
                douyin TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS necklaces (
                token TEXT PRIMARY KEY,
                owner_id INTEGER REFERENCES users(id),
                bound_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at INTEGER NOT NULL
            );
            """
        )

        legacy_profiles = connection.execute(
            """
            SELECT p.*
            FROM profiles p
            LEFT JOIN device_profiles d ON d.user_id = p.user_id
            WHERE d.token IS NULL
            """
        ).fetchall()
        for legacy in legacy_profiles:
            owned_tokens = connection.execute(
                "SELECT token FROM necklaces WHERE owner_id = ? ORDER BY bound_at DESC, token ASC",
                (legacy["user_id"],),
            ).fetchall()
            for owned in owned_tokens:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO device_profiles(
                        token, user_id, slug, name, avatar, bio, tags, wechat, wechat_qr, douyin
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        owned["token"],
                        legacy["user_id"],
                        unique_device_slug(connection, legacy["name"]),
                        legacy["name"],
                        legacy["avatar"],
                        legacy["bio"],
                        legacy["tags"],
                        legacy["wechat"],
                        legacy["wechat_qr"],
                        legacy["douyin"],
                    ),
                )
def now() -> int:
    return int(time.time())


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$", 2)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 180_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def slugify(value: str, fallback: str) -> str:
    cleaned = "".join(char.lower() for char in value if char.isalnum() or char in "-_")
    return cleaned[:36] or fallback


def unique_device_slug(connection: sqlite3.Connection, name: str) -> str:
    base = slugify(name.replace(" ", "-"), f"member-{secrets.token_hex(3)}")
    candidate = base
    index = 1
    while connection.execute("SELECT 1 FROM device_profiles WHERE slug = ?", (candidate,)).fetchone():
        index += 1
        candidate = f"{base[:30]}-{index}"
    return candidate


def public_profile(row: sqlite3.Row | None) -> dict | None:
    if row is None or not row["slug"]:
        return None
    return {
        "slug": row["slug"],
        "name": row["name"],
        "avatar": row["avatar"],
        "bio": row["bio"],
        "tags": json.loads(row["tags"] or "[]"),
        "wechat": row["wechat"],
        "wechatQr": row["wechat_qr"],
        "douyin": row["douyin"],
    }


def device_profile_defaults(name: str, source: sqlite3.Row | None = None) -> dict:
    base_name = name.strip()[:28] or (source["name"] if source and source["name"] else "未命名")
    return {
        "name": base_name,
        "avatar": source["avatar"] if source else "",
        "bio": source["bio"] if source else "",
        "tags": source["tags"] if source else "[]",
        "wechat": source["wechat"] if source else "",
        "wechat_qr": source["wechat_qr"] if source else "",
        "douyin": source["douyin"] if source else "",
    }


def profile_for_token(connection: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM device_profiles WHERE token = ?", (token,)).fetchone()


def primary_profile_for_user(connection: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT p.*
        FROM device_profiles p
        JOIN necklaces n ON n.token = p.token
        WHERE p.user_id = ?
        ORDER BY n.bound_at DESC, n.token ASC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def ensure_device_profile(
    connection: sqlite3.Connection,
    user_id: int,
    token: str,
    name: str,
    source: sqlite3.Row | None = None,
) -> sqlite3.Row:
    existing = profile_for_token(connection, token)
    if existing is not None:
        return existing
    defaults = device_profile_defaults(name, source)
    connection.execute(
        """
        INSERT INTO device_profiles(
            token, user_id, slug, name, avatar, bio, tags, wechat, wechat_qr, douyin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            user_id,
            unique_device_slug(connection, defaults["name"]),
            defaults["name"],
            defaults["avatar"],
            defaults["bio"],
            defaults["tags"],
            defaults["wechat"],
            defaults["wechat_qr"],
            defaults["douyin"],
        ),
    )
    return profile_for_token(connection, token)


def device_payload(token: str, profile: dict | None, bound_at: int | None) -> dict:
    return {
        "token": token,
        "bound": profile is not None,
        "boundAt": bound_at,
        "profile": profile,
        "publicUrl": f"/tap/{token}",
    }


class TapHandler(BaseHTTPRequestHandler):
    server_version = "NEXTOUCH/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/tap/"):
            self.get_tap(unquote(path.removeprefix("/api/tap/")))
            return
        if path == "/api/me":
            self.get_me()
            return
        if path.startswith("/api/profile/"):
            self.get_profile(unquote(path.removeprefix("/api/profile/")))
            return
        if path.startswith("/tap/") or path.startswith("/u/") or path.startswith("/account"):
            self.serve_file(ROOT / "index.html")
            return
        self.serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/register":
            self.register()
            return
        if path == "/api/login":
            self.login()
            return
        if path == "/api/logout":
            self.logout()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/profile":
            self.update_profile()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        return

    def serve_static(self, path: str) -> None:
        safe_path = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (ROOT / safe_path).resolve()
        if ROOT not in target.parents and target != ROOT:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.serve_file(target)

    def serve_file(self, target: Path) -> None:
        payload = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(payload)))
        if content_type.startswith("text/"):
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except json.JSONDecodeError:
            return {}

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK, cookie: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def session_token(self) -> str | None:
        cookies = SimpleCookie(self.headers.get("Cookie"))
        morsel = cookies.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def current_user(self) -> sqlite3.Row | None:
        token = self.session_token()
        if not token:
            return None
        with connect() as connection:
            return connection.execute(
                """
                SELECT users.id, users.email
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()

    def profile_for_user(self, connection: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
        return connection.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()

    def get_tap(self, token: str) -> None:
        with connect() as connection:
            necklace = connection.execute("SELECT * FROM necklaces WHERE token = ?", (token,)).fetchone()
            if necklace is None:
                connection.execute(
                    "INSERT INTO necklaces(token, owner_id, bound_at) VALUES (?, NULL, NULL)",
                    (token,),
                )
                necklace = connection.execute("SELECT * FROM necklaces WHERE token = ?", (token,)).fetchone()
            profile = profile_for_token(connection, token)
            if necklace["owner_id"] and profile is None:
                profile = ensure_device_profile(connection, necklace["owner_id"], token, "NEXTOUCH")
        self.send_json(
            {
                "token": token,
                "bound": bool(necklace["owner_id"]),
                "profile": public_profile(profile),
                "me": self.me_payload(),
            }
        )

    def get_me(self) -> None:
        self.send_json({"me": self.me_payload()})

    def get_profile(self, slug: str) -> None:
        with connect() as connection:
            profile = connection.execute("SELECT * FROM device_profiles WHERE slug = ?", (slug,)).fetchone()
        if profile is None:
            self.send_json({"error": "主页不存在。"}, HTTPStatus.NOT_FOUND)
            return
        self.send_json({"profile": public_profile(profile)})

    def me_payload(self) -> dict | None:
        user = self.current_user()
        if user is None:
            return None
        return self.user_payload(user["id"], user["email"])

    def user_payload(self, user_id: int, email: str | None = None, focus_token: str | None = None) -> dict:
        with connect() as connection:
            if email is None:
                user = connection.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
                email = user["email"] if user else ""
            necklaces = connection.execute(
                "SELECT token, bound_at FROM necklaces WHERE owner_id = ? ORDER BY bound_at DESC, token ASC",
                (user_id,),
            ).fetchall()
            device_rows = []
            for necklace in necklaces:
                profile = profile_for_token(connection, necklace["token"])
                if profile is None:
                    profile = ensure_device_profile(connection, user_id, necklace["token"], "NEXTOUCH")
                device_rows.append((necklace, profile))
            profile = None
            if focus_token:
                for necklace, profile_row in device_rows:
                    if necklace["token"] == focus_token:
                        profile = profile_row
                        break
            if profile is None and device_rows:
                profile = device_rows[0][1]
        return {
            "id": user_id,
            "email": email,
            "profile": public_profile(profile),
            "necklaceToken": necklaces[0]["token"] if necklaces else None,
            "devices": [
                device_payload(row["token"], public_profile(profile_row), row["bound_at"])
                for row, profile_row in device_rows
            ],
        }

    def register(self) -> None:
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        name = str(data.get("name", "")).strip()[:28]
        token = str(data.get("token", "")).strip()
        if "@" not in email or len(password) < 6 or not name:
            self.send_json({"error": "请填写昵称、邮箱和至少 6 位密码。"}, HTTPStatus.BAD_REQUEST)
            return

        with connect() as connection:
            necklace = None
            if token:
                necklace = connection.execute("SELECT * FROM necklaces WHERE token = ?", (token,)).fetchone()
                if necklace is None or necklace["owner_id"]:
                    self.send_json({"error": "这条项链已经绑定，或当前入口无效。"}, HTTPStatus.CONFLICT)
                    return
            try:
                cursor = connection.execute(
                    "INSERT INTO users(email, password_hash, created_at) VALUES (?, ?, ?)",
                    (email, hash_password(password), now()),
                )
            except sqlite3.IntegrityError:
                self.send_json({"error": "这个邮箱已经注册，请直接登录。"}, HTTPStatus.CONFLICT)
                return
            user_id = cursor.lastrowid
            if token:
                connection.execute(
                    "UPDATE necklaces SET owner_id = ?, bound_at = ? WHERE token = ?",
                    (user_id, now(), token),
                )
                ensure_device_profile(connection, user_id, token, name)
            session = self.new_session(connection, user_id)
        self.send_json(
            {"me": self.user_payload(user_id, email, token or None)},
            HTTPStatus.CREATED,
            self.cookie_header(session),
        )
    def login(self) -> None:
        data = self.read_json()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        token = str(data.get("token", "")).strip()
        with connect() as connection:
            user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user is None or not verify_password(password, user["password_hash"]):
                self.send_json({"error": "邮箱或密码不正确。"}, HTTPStatus.UNAUTHORIZED)
                return
            if token:
                necklace = connection.execute("SELECT * FROM necklaces WHERE token = ?", (token,)).fetchone()
                if necklace and necklace["owner_id"] is None:
                    connection.execute(
                        "UPDATE necklaces SET owner_id = ?, bound_at = ? WHERE token = ?",
                        (user["id"], now(), token),
                    )
                    ensure_device_profile(connection, user["id"], token, user["email"], primary_profile_for_user(connection, user["id"]))
                elif necklace and necklace["owner_id"] not in (None, user["id"]):
                    self.send_json({"error": "这条项链已经绑定到另一个账号。"}, HTTPStatus.CONFLICT)
                    return
            session = self.new_session(connection, user["id"])
        self.send_json(
            {"me": self.user_payload(user["id"], user["email"], token or None)},
            cookie=self.cookie_header(session),
        )
    def logout(self) -> None:
        token = self.session_token()
        if token:
            with connect() as connection:
                connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        self.send_json({"ok": True}, cookie=f"{SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax")

    def update_profile(self) -> None:
        user = self.current_user()
        if user is None:
            self.send_json({"error": "请先登录。"}, HTTPStatus.UNAUTHORIZED)
            return
        data = self.read_json()
        tags = [str(tag).strip()[:18] for tag in data.get("tags", []) if str(tag).strip()][:6]
        token = str(data.get("token", "")).strip()
        if not token:
            self.send_json({"error": "缺少设备编号。"}, HTTPStatus.BAD_REQUEST)
            return
        with connect() as connection:
            necklace = connection.execute(
                "SELECT * FROM necklaces WHERE token = ? AND owner_id = ?",
                (token, user["id"]),
            ).fetchone()
            if necklace is None:
                self.send_json({"error": "这条项链不属于当前账号。"}, HTTPStatus.FORBIDDEN)
                return
            profile = profile_for_token(connection, token)
            if profile is None:
                profile = ensure_device_profile(
                    connection,
                    user["id"],
                    token,
                    str(data.get("name", "")).strip(),
                    primary_profile_for_user(connection, user["id"]),
                )
            connection.execute(
                """
                UPDATE device_profiles
                SET name = ?, avatar = ?, bio = ?, tags = ?, wechat = ?, wechat_qr = ?, douyin = ?
                WHERE token = ?
                """,
                (
                    str(data.get("name", "")).strip()[:28] or "未命名",
                    str(data.get("avatar", "")).strip(),
                    str(data.get("bio", "")).strip()[:120],
                    json.dumps(tags, ensure_ascii=False),
                    str(data.get("wechat", "")).strip()[:48],
                    str(data.get("wechatQr", "")).strip(),
                    str(data.get("douyin", "")).strip(),
                    token,
                ),
            )
        self.send_json({"me": self.user_payload(user["id"], user["email"], token)})
    def unique_slug(self, connection: sqlite3.Connection, name: str) -> str:
        base = slugify(name.replace(" ", "-"), f"member-{secrets.token_hex(3)}")
        candidate = base
        index = 1
        while connection.execute("SELECT 1 FROM profiles WHERE slug = ?", (candidate,)).fetchone():
            index += 1
            candidate = f"{base[:30]}-{index}"
        return candidate

    def new_session(self, connection: sqlite3.Connection, user_id: int) -> str:
        token = secrets.token_urlsafe(24)
        connection.execute(
            "INSERT INTO sessions(token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, now()),
        )
        return token

    def cookie_header(self, token: str) -> str:
        return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax"


if __name__ == "__main__":
    init_db()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "4173"))
    server = ThreadingHTTPServer((host, port), TapHandler)
    print(f"NEXTOUCH server running at http://{host}:{port}")
    server.serve_forever()
