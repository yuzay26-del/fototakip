"""SQLite bağlantısı, şema ve küçük yardımcılar.

Yalnızca Python standart kütüphanesi kullanılır; Termux'ta derleme gerektiren paket yoktur.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = 4

SCHEMA = """
CREATE TABLE users (
    id          TEXT PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name        TEXT NOT NULL,
    short       TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('manager', 'field')),
    pw_hash     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE sessions (
    token       TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    short       TEXT NOT NULL,
    client      TEXT NOT NULL DEFAULT '',
    contact     TEXT NOT NULL DEFAULT '',
    address     TEXT NOT NULL DEFAULT '',
    lat         REAL,
    lng         REAL,
    created_at  TEXT NOT NULL
);
CREATE TABLE tasks (
    id              TEXT PRIMARY KEY,
    no              INTEGER NOT NULL UNIQUE,
    project_id      TEXT NOT NULL REFERENCES projects(id),
    title           TEXT NOT NULL,
    untitled        INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL CHECK (status IN ('open', 'progress', 'review', 'done')),
    assignee_id     TEXT REFERENCES users(id),
    due             TEXT NOT NULL,
    priority        TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('normal', 'high')),
    rejected_reason TEXT,
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE photos (
    id          TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL UNIQUE,
    path        TEXT NOT NULL,
    thumb_path  TEXT NOT NULL,
    mime        TEXT NOT NULL,
    width       INTEGER,
    height      INTEGER,
    taken_at    TEXT NOT NULL,
    lat         REAL,
    lng         REAL,
    gps_source  TEXT NOT NULL DEFAULT 'none' CHECK (gps_source IN ('exif', 'device', 'project', 'none')),
    uploaded_by TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE task_photos (
    task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    photo_id    TEXT NOT NULL REFERENCES photos(id),
    type        TEXT NOT NULL CHECK (type IN ('before', 'progress', 'after', 'issue')),
    created_at  TEXT NOT NULL,
    PRIMARY KEY (task_id, photo_id)
);
CREATE TABLE annotations (
    id          TEXT PRIMARY KEY,
    photo_id    TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    x           REAL NOT NULL CHECK (x BETWEEN 0 AND 100),
    y           REAL NOT NULL CHECK (y BETWEEN 0 AND 100),
    text        TEXT NOT NULL,
    by_id       TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE comments (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    by_id       TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE checklist (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    done            INTEGER NOT NULL DEFAULT 0,
    require_proof   INTEGER NOT NULL DEFAULT 0,
    proof_photo_id  TEXT REFERENCES photos(id),
    sort            INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE activity (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    by_id       TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE signatures (
    task_id     TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    signer      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX idx_tp_photo ON task_photos(photo_id);
CREATE INDEX idx_activity_task ON activity(task_id);
INSERT INTO settings(key, value) VALUES ('auto_rule', '1'), ('next_no', '1');
"""

# Sürüm sürüm göçler. Var olan veriler korunur; yalnızca sütun ve tablo eklenir.
MIGRATIONS = {
    2: """
    ALTER TABLE photos ADD COLUMN gps_accuracy REAL;
    ALTER TABLE photos ADD COLUMN address TEXT;
    ALTER TABLE projects ADD COLUMN address_source TEXT NOT NULL DEFAULT 'manual';
    ALTER TABLE projects ADD COLUMN location_source TEXT NOT NULL DEFAULT 'manual';
    ALTER TABLE projects ADD COLUMN suggested_address TEXT;
    CREATE TABLE geocode_cache (
        key         TEXT PRIMARY KEY,
        address     TEXT NOT NULL,
        raw         TEXT NOT NULL,
        created_at  TEXT NOT NULL
    );
    UPDATE projects SET location_source = 'none' WHERE lat IS NULL;
    UPDATE projects SET address_source = 'none' WHERE address = '';
    """,
    3: """
    CREATE TABLE ai_reviews (
        photo_id    TEXT PRIMARY KEY REFERENCES photos(id) ON DELETE CASCADE,
        model       TEXT NOT NULL,
        result      TEXT NOT NULL,
        by_id       TEXT NOT NULL,
        created_at  TEXT NOT NULL
    );
    INSERT OR IGNORE INTO settings(key, value) VALUES ('ai_enabled', '0'), ('ai_model', 'gpt-4.1-mini'),
        ('tunnel_mode', 'off'), ('tunnel_hostname', ''), ('tunnel_autostart', '0');
    """,
    # 4: rol hiyerarşisi (sahip/yönetici/ekip lideri/teknisyen), ekipler, yetenekler, müşteri ayrıntıları.
    # users tablosundaki rol kısıtı değiştiği için tablo yeniden kurulur (veriler kopyalanır).
    4: """
    CREATE TABLE users_new (
        id          TEXT PRIMARY KEY,
        username    TEXT NOT NULL UNIQUE COLLATE NOCASE,
        name        TEXT NOT NULL,
        short       TEXT NOT NULL,
        role        TEXT NOT NULL CHECK (role IN ('owner', 'manager', 'lead', 'field')),
        pw_hash     TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        lead_id     TEXT REFERENCES users(id) ON DELETE SET NULL,
        phone       TEXT NOT NULL DEFAULT '',
        active      INTEGER NOT NULL DEFAULT 1,
        theme       TEXT NOT NULL DEFAULT ''
    );
    INSERT INTO users_new(id, username, name, short, role, pw_hash, created_at)
        SELECT id, username, name, short, role, pw_hash, created_at FROM users;
    DROP TABLE users;
    ALTER TABLE users_new RENAME TO users;
    CREATE INDEX idx_users_lead ON users(lead_id);
    UPDATE users SET role = 'owner' WHERE id = (SELECT id FROM users WHERE role = 'manager' ORDER BY created_at LIMIT 1);
    ALTER TABLE projects ADD COLUMN phone TEXT NOT NULL DEFAULT '';
    ALTER TABLE projects ADD COLUMN email TEXT NOT NULL DEFAULT '';
    ALTER TABLE projects ADD COLUMN notes TEXT NOT NULL DEFAULT '';
    ALTER TABLE projects ADD COLUMN archived INTEGER NOT NULL DEFAULT 0;
    CREATE TABLE skills (
        id      TEXT PRIMARY KEY,
        name    TEXT NOT NULL UNIQUE COLLATE NOCASE,
        icon    TEXT NOT NULL DEFAULT 'wrench',
        color   TEXT NOT NULL DEFAULT '#64748B',
        sort    INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE user_skills (
        user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        skill_id  TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
        PRIMARY KEY (user_id, skill_id)
    );
    ALTER TABLE tasks ADD COLUMN skill_id TEXT REFERENCES skills(id) ON DELETE SET NULL;
    INSERT INTO skills(id, name, icon, color, sort) VALUES
        ('sk_elektrik', 'Elektrik', 'bolt', '#D97706', 1),
        ('sk_tesisat', 'Tesisat', 'drop', '#0284C7', 2),
        ('sk_klima', 'Klima', 'snow', '#0891B2', 3),
        ('sk_boya', 'Boya', 'brush', '#C026D3', 4),
        ('sk_yapi', 'Yapı', 'brick', '#B45309', 5),
        ('sk_ag', 'Ağ ve telekom', 'wifi', '#4F46E5', 6)
    """,
}
# Tablo yeniden kurulan göçler: yabancı anahtar denetimi göç süresince kapatılır, sonra doğrulanır.
REBUILD_MIGRATIONS = {4}

# SQLite aynı anda tek yazıcıya izin verir; yazmaları süreç içinde sıraya sokuyoruz.
WRITE_LOCK = threading.RLock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=15, isolation_level=None, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 15000")
    return con


def init(path: str) -> None:
    con = connect(path)
    try:
        con.execute("PRAGMA journal_mode = WAL")
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Veritabanı sürümü ({version}) bu uygulamadan ({SCHEMA_VERSION}) yeni. Uygulamayı güncelle."
            )
        if version == 0:
            con.executescript(SCHEMA)
            con.execute("PRAGMA user_version = 1")
            version = 1
        for target in range(version + 1, SCHEMA_VERSION + 1):
            rebuild = target in REBUILD_MIGRATIONS
            if rebuild:  # DROP TABLE, bağlı satırları silmesin (oturumlar, işler)
                con.execute("PRAGMA foreign_keys = OFF")
            con.execute("BEGIN IMMEDIATE")
            try:
                for stmt in [x.strip() for x in MIGRATIONS[target].split(";") if x.strip()]:
                    con.execute(stmt)
                if rebuild:
                    bad = con.execute("PRAGMA foreign_key_check").fetchall()
                    if bad:
                        raise RuntimeError(f"Göç {target}: yabancı anahtar hatası {[tuple(r) for r in bad[:3]]}")
                con.execute(f"PRAGMA user_version = {target}")
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
            finally:
                if rebuild:
                    con.execute("PRAGMA foreign_keys = ON")
    finally:
        con.close()


@contextlib.contextmanager
def tx(con: sqlite3.Connection):
    """Yazma işlemi: süreç içi kilit + BEGIN IMMEDIATE."""
    with WRITE_LOCK:
        con.execute("BEGIN IMMEDIATE")
        try:
            yield con
        except BaseException:
            con.execute("ROLLBACK")
            raise
        else:
            con.execute("COMMIT")


def setting(con: sqlite3.Connection, key: str, default: str = "") -> str:
    row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(con: sqlite3.Connection, key: str, value: str) -> None:
    con.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def next_task_no(con: sqlite3.Connection) -> int:
    n = int(setting(con, "next_no", "1"))
    set_setting(con, "next_no", str(n + 1))
    return n


def is_empty(path: str) -> bool:
    con = connect(path)
    try:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    finally:
        con.close()
