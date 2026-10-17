import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import sys
if getattr(sys, 'frozen', False):
    DB_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "helpdesk.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str, salt: str = "helpdesk_salt_2026") -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def init_admin_auth():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    if count == 0:
        default_user = os.getenv("ADMIN_USERNAME", "admin").strip()
        default_pass = os.getenv("ADMIN_PASSWORD", "admin123").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT OR IGNORE INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                       (default_user, hash_password(default_pass), now))
        conn.commit()
    conn.close()

def get_all_users() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, created_at FROM users ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def create_user(username: str, password: str, role: str = "agent") -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                   (username.strip(), hash_password(password), role, now))
    conn.commit()
    user_id = cursor.lastrowid
    cursor.execute("SELECT id, username, role, created_at FROM users WHERE id = ?", (user_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

def delete_user(user_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def verify_user_credentials(username: str, password: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, role, created_at FROM users WHERE username = ?", (username.strip(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    if row["password_hash"] == hash_password(password):
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None

def update_user_password(username: str, new_password: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                   (hash_password(new_password), username.strip()))
    conn.commit()
    conn.close()

def create_session(username: str) -> str:
    token = secrets.token_hex(24)
    now = datetime.now()
    expires = (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (token, username, created_at, expires_at) VALUES (?, ?, ?, ?)",
                   (token, username, now.strftime("%Y-%m-%d %H:%M:%S"), expires))
    conn.commit()
    conn.close()
    return token

def verify_session(token: str) -> Optional[str]:
    if not token:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, expires_at FROM sessions WHERE token = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    
    expires_str = row["expires_at"]
    if datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S") < datetime.now():
        delete_session(token)
        return None
    return row["username"]

def delete_session(token: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT DEFAULT 'agent',
        created_at TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT UNIQUE,
        telegram_chat_id INTEGER,
        telegram_user_id INTEGER,
        user_name TEXT,
        username TEXT,
        phone_number TEXT DEFAULT '',
        chat_type TEXT DEFAULT 'private',
        chat_title TEXT DEFAULT '',
        status TEXT DEFAULT 'open',
        subject TEXT DEFAULT '',
        last_message_id INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        closed_at TEXT
    )
    """)
    
    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN last_message_id INTEGER DEFAULT 0")
    except Exception:
        pass
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        sender_type TEXT,
        sender_name TEXT,
        text TEXT,
        media_type TEXT DEFAULT 'text',
        media_url TEXT DEFAULT '',
        created_at TEXT,
        telegram_message_id INTEGER DEFAULT 0,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        username TEXT,
        created_at TEXT,
        expires_at TEXT
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user_status ON tickets(telegram_user_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_ticket_id ON messages(ticket_id)")
    
    conn.commit()
    conn.close()
    
    init_admin_auth()

def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_active_ticket_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Returns the user's active open or in_progress ticket. Never returns resolved/closed tickets."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tickets 
        WHERE telegram_user_id = ? AND status IN ('open', 'in_progress')
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_ticket(telegram_chat_id: int, telegram_user_id: int, user_name: str, 
                  username: str, phone_number: str = "", chat_type: str = "private", 
                  chat_title: str = "", subject: str = "", last_message_id: int = 0) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO tickets (telegram_chat_id, telegram_user_id, user_name, username, 
                             phone_number, chat_type, chat_title, status, subject, last_message_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
    """, (telegram_chat_id, telegram_user_id, user_name, username, phone_number, chat_type, chat_title, subject, last_message_id, now, now))
    
    ticket_id = cursor.lastrowid
    ticket_number = f"TK-{1000 + ticket_id}"
    
    cursor.execute("UPDATE tickets SET ticket_number = ? WHERE id = ?", (ticket_number, ticket_id))
    conn.commit()
    
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = dict(cursor.fetchone())
    conn.close()
    return ticket

def update_ticket_last_message_id(ticket_id: int, message_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET last_message_id = ? WHERE id = ?", (message_id, ticket_id))
    conn.commit()
    conn.close()

def update_ticket_phone(ticket_id: int, phone_number: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET phone_number = ?, updated_at = ? WHERE id = ?", (phone_number, now, ticket_id))
    conn.commit()
    conn.close()

def update_ticket_status(ticket_id: int, status: str) -> Optional[Dict[str, Any]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Unify resolved to closed
    if status == 'resolved':
        status = 'closed'

    closed_at = now if status == 'closed' else None
    conn = get_db()
    cursor = conn.cursor()
    
    # Ensure closed tickets cannot be reopened
    cursor.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,))
    curr = cursor.fetchone()
    if curr and curr["status"] in ('resolved', 'closed') and status not in ('resolved', 'closed'):
        conn.close()
        raise ValueError("Closed tickets cannot be reopened. A new ticket must be created.")

    cursor.execute("""
        UPDATE tickets 
        SET status = ?, updated_at = ?, closed_at = COALESCE(?, closed_at)
        WHERE id = ?
    """, (status, now, closed_at, ticket_id))
    conn.commit()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_message(ticket_id: int, sender_type: str, sender_name: str, text: str, 
                media_type: str = "text", media_url: str = "", telegram_message_id: int = 0) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (ticket_id, sender_type, sender_name, text, media_type, media_url, created_at, telegram_message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, sender_type, sender_name, text, media_type, media_url, now, telegram_message_id))
    msg_id = cursor.lastrowid
    
    # Update ticket updated_at
    cursor.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (now, ticket_id))
    conn.commit()
    
    cursor.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
    msg = dict(cursor.fetchone())
    conn.close()
    return msg

def get_all_tickets(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT t.*, 
               (SELECT text FROM messages WHERE ticket_id = t.id ORDER BY id DESC LIMIT 1) as last_message,
               (SELECT created_at FROM messages WHERE ticket_id = t.id ORDER BY id DESC LIMIT 1) as last_message_time,
               (SELECT COUNT(*) FROM messages WHERE ticket_id = t.id) as message_count
        FROM tickets t
    """
    params = []
    if status_filter and status_filter != 'all':
        if status_filter in ('closed', 'resolved'):
            query += " WHERE t.status IN ('closed', 'resolved')"
        else:
            query += " WHERE t.status = ?"
            params.append(status_filter)
        
    query += " ORDER BY t.updated_at DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_ticket_details(ticket_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket_row = cursor.fetchone()
    if not ticket_row:
        conn.close()
        return None
    
    ticket = dict(ticket_row)
    cursor.execute("SELECT * FROM messages WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,))
    ticket["messages"] = [dict(m) for m in cursor.fetchall()]
    conn.close()
    return ticket

def get_stats() -> Dict[str, int]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")
    open_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'in_progress'")
    in_progress_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('resolved', 'closed')")
    closed_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets")
    total_count = cursor.fetchone()[0]
    conn.close()
    return {
        "open": open_count,
        "in_progress": in_progress_count,
        "closed": closed_count,
        "total": total_count
    }
