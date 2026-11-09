"""Parola özeti ve oturumlar."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from . import db

ITERATIONS = 200_000
SESSION_DAYS = 30


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_session(con, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    with db.tx(con):
        con.execute(
            "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, db.now(), expires),
        )
        con.execute("DELETE FROM sessions WHERE expires_at < ?", (db.now(),))
    return token


def user_for_token(con, token: str | None):
    if not token:
        return None
    row = con.execute(
        "SELECT u.id, u.username, u.name, u.short, u.role, u.lead_id, u.theme FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token = ? AND s.expires_at > ? AND u.active = 1",
        (token, db.now()),
    ).fetchone()
    return dict(row) if row else None


def delete_session(con, token: str) -> None:
    with db.tx(con):
        con.execute("DELETE FROM sessions WHERE token = ?", (token,))


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
