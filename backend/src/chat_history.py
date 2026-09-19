from pathlib import Path
import sqlite3
import uuid
from datetime import datetime, timezone
import json

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "storage" / "chat_history.db"


def _db_path(storage_dir=None):
    if storage_dir:
        path = Path(storage_dir) / "chat_history.db"
    else:
        path = DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(storage_dir=None):
    conn = sqlite3.connect(_db_path(storage_dir))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(storage_dir=None):
    with _connect(storage_dir) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources_json TEXT,
            retrieval_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages(conversation_id, id);
        """)


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_conversation(title="New conversation", storage_dir=None):
    conversation_id = str(uuid.uuid4())
    now = _now()
    with _connect(storage_dir) as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conversation_id, title[:100] or "New conversation", now, now),
        )
    return conversation_id


def list_conversations(storage_dir=None):
    with _connect(storage_dir) as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation(conversation_id, storage_dir=None):
    with _connect(storage_dir) as conn:
        conversation = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if conversation is None:
            return None
        messages = conn.execute(
            "SELECT role, content, sources_json, retrieval_json, created_at "
            "FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    result = dict(conversation)
    result["messages"] = []
    for row in messages:
        item = {"role": row["role"], "content": row["content"]}
        if row["sources_json"]:
            item["sources"] = json.loads(row["sources_json"])
        if row["retrieval_json"]:
            item["retrieval"] = json.loads(row["retrieval_json"])
        result["messages"].append(item)
    return result


def add_message(conversation_id, role, content, sources=None, retrieval=None, storage_dir=None):
    now = _now()
    with _connect(storage_dir) as conn:
        conn.execute(
            "INSERT INTO messages "
            "(conversation_id, role, content, sources_json, retrieval_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                conversation_id, role, content,
                json.dumps(sources, ensure_ascii=False) if sources is not None else None,
                json.dumps(retrieval, ensure_ascii=False) if retrieval is not None else None,
                now,
            ),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )


def ensure_conversation(conversation_id=None, title="New conversation", storage_dir=None):
    if conversation_id:
        with _connect(storage_dir) as conn:
            row = conn.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row:
            return conversation_id
    return create_conversation(title, storage_dir)


def delete_conversation(conversation_id, storage_dir=None):
    with _connect(storage_dir) as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    return cur.rowcount > 0
