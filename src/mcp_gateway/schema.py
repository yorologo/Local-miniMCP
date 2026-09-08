import sqlite3
import os

SCHEMA_V1 = """
-- targets
CREATE TABLE targets (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'linux',
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 22,
    user TEXT NOT NULL,
    ssh_alias TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- projects
CREATE TABLE projects (
    id TEXT NOT NULL,
    target_id TEXT NOT NULL REFERENCES targets(id),
    display_name TEXT NOT NULL,
    root TEXT NOT NULL,
    read_enabled INTEGER NOT NULL DEFAULT 1,
    write_enabled INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (target_id, id)
);

-- project_tasks
CREATE TABLE project_tasks (
    target_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    argv_json TEXT NOT NULL,  -- JSON array of strings
    timeout INTEGER NOT NULL DEFAULT 30,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (target_id, project_id, task_name),
    FOREIGN KEY (target_id, project_id) REFERENCES projects(target_id, id)
);

-- ai_clients
CREATE TABLE ai_clients (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT '',
    protocol TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- grants
CREATE TABLE grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL REFERENCES ai_clients(id),
    target_id TEXT NOT NULL REFERENCES targets(id),
    project_id TEXT,
    capability TEXT NOT NULL DEFAULT 'read',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- activity
CREATE TABLE activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    actor TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    target_id TEXT,
    project_id TEXT,
    duration_ms INTEGER,
    success INTEGER NOT NULL DEFAULT 1,
    error_code TEXT,
    bytes_transferred INTEGER,
    detail TEXT NOT NULL DEFAULT ''
);

-- settings
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- admin_users
CREATE TABLE admin_users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login TEXT
);

PRAGMA user_version = 1;
"""


def init_db(db_path: str):
    # Ensure dir exists
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    try:
        migrate_db(conn)
    finally:
        conn.close()

def get_schema_version(conn: sqlite3.Connection) -> int:
    cursor = conn.cursor()
    cursor.execute("PRAGMA user_version")
    return cursor.fetchone()[0]

def migrate_db(conn: sqlite3.Connection):
    current_version = get_schema_version(conn)
    if current_version == 0:
        cursor = conn.cursor()
        cursor.executescript(SCHEMA_V1)

    # Insert default settings if missing
    defaults = [
        ("gateway_enabled", "true"),
        ("writes_enabled", "false"),
        ("default_timeout", "30"),
        ("max_output_bytes", "262144"),
        ("max_file_read_bytes", "1048576"),
        ("max_write_bytes", "262144"),
        ("max_diff_bytes", "65536"),
        ("activity_retention", "5000"),
    ]

    cursor = conn.cursor()
    cursor.executemany(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        defaults
    )
    conn.commit()

