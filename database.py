import sqlite3
import os
import re
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
    
    columns_to_add = [
        ("last_message_id", "INTEGER DEFAULT 0"),
        ("assigned_to", "TEXT DEFAULT NULL"),
        ("assigned_at", "TEXT DEFAULT NULL"),
        ("priority", "TEXT DEFAULT 'medium'"),
        ("category", "TEXT DEFAULT 'General'"),
        ("first_response_at", "TEXT DEFAULT NULL"),
        ("sla_deadline", "TEXT DEFAULT NULL"),
        ("sla_breached", "INTEGER DEFAULT 0"),
        ("sla_warning_sent", "INTEGER DEFAULT 0"),
        ("sla_breach_sent", "INTEGER DEFAULT 0"),
        ("rating", "INTEGER DEFAULT NULL"),
        ("rating_comment", "TEXT DEFAULT NULL"),
        ("rated_at", "TEXT DEFAULT NULL"),
    ]
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_type}")
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
        is_internal INTEGER DEFAULT 0,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
    )
    """)
    
    msg_cols = [("is_internal", "INTEGER DEFAULT 0")]
    for col_name, col_type in msg_cols:
        try:
            cursor.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS canned_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        text TEXT,
        category TEXT DEFAULT 'General',
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faq_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keywords TEXT,
        question TEXT,
        answer TEXT,
        is_active INTEGER DEFAULT 1,
        helpful_count INTEGER DEFAULT 0,
        created_at TEXT
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
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profiles (
        telegram_user_id INTEGER PRIMARY KEY,
        user_name TEXT,
        username TEXT,
        phone_number TEXT,
        updated_at TEXT
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user_status ON tickets(telegram_user_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_ticket_id ON messages(ticket_id)")
    # Ensure default telegram bot token if not set
    default_token = os.getenv("TELEGRAM_BOT_TOKEN", "8825356962:AAH-IwHd43WBNSp34un-RVoQD2w3IjKwlbs").strip()
    cursor.execute("SELECT value FROM settings WHERE key = 'telegram_bot_token'")
    row = cursor.fetchone()
    if not row or not row["value"]:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('telegram_bot_token', ?)", (default_token,))

    conn.commit()
    conn.close()
    
    init_admin_auth()
    init_default_canned_responses()
    init_default_faqs()

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

SLA_HOURS = {
    "critical": 2,
    "high": 6,
    "medium": 24,
    "low": 48
}

def calculate_sla_deadline(created_at_str: str, priority: str = "medium") -> str:
    try:
        dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        dt = datetime.now()
    hours = SLA_HOURS.get((priority or "medium").lower(), 24)
    deadline = dt + timedelta(hours=hours)
    return deadline.strftime("%Y-%m-%d %H:%M:%S")

def save_user_profile(telegram_user_id: int, user_name: str = "", username: str = "", phone_number: str = ""):
    if not telegram_user_id:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profiles WHERE telegram_user_id = ?", (telegram_user_id,))
    row = cursor.fetchone()
    if row:
        current_phone = row["phone_number"] or ""
        phone = phone_number.strip() if phone_number else current_phone
        name = user_name.strip() if user_name else (row["user_name"] or "")
        uname = username.strip() if username else (row["username"] or "")
        cursor.execute("""
            UPDATE user_profiles 
            SET user_name = ?, username = ?, phone_number = ?, updated_at = ?
            WHERE telegram_user_id = ?
        """, (name, uname, phone, now, telegram_user_id))
    else:
        cursor.execute("""
            INSERT INTO user_profiles (telegram_user_id, user_name, username, phone_number, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_user_id, user_name, username, phone_number, now))
    conn.commit()
    conn.close()

def get_user_profile(telegram_user_id: int) -> Optional[Dict[str, Any]]:
    if not telegram_user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profiles WHERE telegram_user_id = ?", (telegram_user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_latest_phone_for_user(telegram_user_id: int) -> str:
    if not telegram_user_id:
        return ""
    conn = get_db()
    cursor = conn.cursor()
    # Check user_profiles table first
    cursor.execute("SELECT phone_number FROM user_profiles WHERE telegram_user_id = ?", (telegram_user_id,))
    row = cursor.fetchone()
    if row and row["phone_number"]:
        conn.close()
        return row["phone_number"].strip()
    # Check historical tickets
    cursor.execute("""
        SELECT phone_number FROM tickets 
        WHERE telegram_user_id = ? AND phone_number IS NOT NULL AND phone_number != ''
        ORDER BY id DESC LIMIT 1
    """, (telegram_user_id,))
    row_t = cursor.fetchone()
    conn.close()
    return row_t["phone_number"].strip() if row_t else ""

def create_ticket(telegram_chat_id: int, telegram_user_id: int, user_name: str, 
                  username: str, phone_number: str = "", chat_type: str = "private", 
                  chat_title: str = "", subject: str = "", last_message_id: int = 0,
                  priority: str = "medium", category: str = "General") -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prio = priority.lower() if priority else "medium"
    if prio not in SLA_HOURS:
        prio = "medium"
    sla_deadline = calculate_sla_deadline(now, prio)
    cat = (category or "General").strip()
    
    # Auto-resolve phone number if not provided from past user profile
    clean_phone = (phone_number or "").strip()
    if not clean_phone and telegram_user_id:
        clean_phone = get_latest_phone_for_user(telegram_user_id)
    elif clean_phone and telegram_user_id:
        save_user_profile(telegram_user_id, user_name, username, clean_phone)
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO tickets (telegram_chat_id, telegram_user_id, user_name, username, 
                             phone_number, chat_type, chat_title, status, subject, 
                             last_message_id, priority, category, sla_deadline, sla_breached, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, 0, ?, ?)
    """, (telegram_chat_id, telegram_user_id, user_name, username, clean_phone, chat_type, 
          chat_title, subject, last_message_id, prio, cat, sla_deadline, now, now))
    
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
    clean_phone = (phone_number or "").strip()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET phone_number = ?, updated_at = ? WHERE id = ?", (clean_phone, now, ticket_id))
    cursor.execute("SELECT telegram_user_id, user_name, username FROM tickets WHERE id = ?", (ticket_id,))
    t_row = cursor.fetchone()
    conn.commit()
    conn.close()
    if t_row and t_row["telegram_user_id"] and clean_phone:
        save_user_profile(t_row["telegram_user_id"], t_row["user_name"] or "", t_row["username"] or "", clean_phone)

def assign_ticket(ticket_id: int, assigned_to: Optional[str]) -> Optional[Dict[str, Any]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assigned_user = assigned_to.strip() if assigned_to else None
    assigned_at = now if assigned_user else None
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tickets 
        SET assigned_to = ?, assigned_at = ?, updated_at = ?
        WHERE id = ?
    """, (assigned_user, assigned_at, now, ticket_id))
    conn.commit()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_ticket_priority(ticket_id: int, priority: str) -> Optional[Dict[str, Any]]:
    prio = priority.lower().strip() if priority else "medium"
    if prio not in SLA_HOURS:
        prio = "medium"
        
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT created_at, status FROM tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    created_at = row["created_at"]
    status = row["status"]
    
    # Recalculate deadline
    new_deadline = calculate_sla_deadline(created_at, prio)
    cursor.execute("""
        UPDATE tickets 
        SET priority = ?, sla_deadline = ?, updated_at = ?
        WHERE id = ?
    """, (prio, new_deadline, now, ticket_id))
    conn.commit()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    updated = cursor.fetchone()
    conn.close()
    return dict(updated) if updated else None

def update_ticket_category(ticket_id: int, category: str) -> Optional[Dict[str, Any]]:
    cat = (category or "General").strip()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tickets 
        SET category = ?, updated_at = ?
        WHERE id = ?
    """, (cat, now, ticket_id))
    conn.commit()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    updated = cursor.fetchone()
    conn.close()
    return dict(updated) if updated else None

def update_ticket_status(ticket_id: int, status: str) -> Optional[Dict[str, Any]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status == 'resolved':
        status = 'closed'

    closed_at = now if status == 'closed' else None
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, sla_deadline FROM tickets WHERE id = ?", (ticket_id,))
    curr = cursor.fetchone()
    if not curr:
        conn.close()
        return None

    sla_breached = 0
    if status == 'closed' and curr["sla_deadline"]:
        try:
            deadline_dt = datetime.strptime(curr["sla_deadline"], "%Y-%m-%d %H:%M:%S")
            now_dt = datetime.now()
            if now_dt > deadline_dt:
                sla_breached = 1
        except Exception:
            sla_breached = 0

    cursor.execute("""
        UPDATE tickets 
        SET status = ?, updated_at = ?, closed_at = ?,
            sla_breached = CASE WHEN ? = 'closed' THEN ? ELSE sla_breached END
        WHERE id = ?
    """, (status, now, closed_at, status, sla_breached, ticket_id))
    conn.commit()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_ticket_rating(ticket_id: int, rating: int, comment: str = "") -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tickets 
        SET rating = ?, rating_comment = ?, rated_at = ?, updated_at = ?
        WHERE id = ?
    """, (rating, comment.strip() if comment else None, now, now, ticket_id))
    conn.commit()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = dict(cursor.fetchone())
    conn.close()
    return ticket

def add_message(ticket_id: int, sender_type: str, sender_name: str, text: str, 
                media_type: str = "text", media_url: str = "", telegram_message_id: int = 0,
                is_internal: int = 0) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (ticket_id, sender_type, sender_name, text, media_type, media_url, created_at, telegram_message_id, is_internal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, sender_type, sender_name, text, media_type, media_url, now, telegram_message_id, is_internal))
    msg_id = cursor.lastrowid
    
    # If external agent reply, record first_response_at if not set
    if sender_type == "agent" and not is_internal:
        cursor.execute("SELECT first_response_at FROM tickets WHERE id = ?", (ticket_id,))
        t_row = cursor.fetchone()
        if t_row and not t_row["first_response_at"]:
            cursor.execute("UPDATE tickets SET first_response_at = ? WHERE id = ?", (now, ticket_id))

    cursor.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (now, ticket_id))
    conn.commit()
    
    cursor.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
    msg = dict(cursor.fetchone())
    conn.close()
    return msg

def add_internal_note(ticket_id: int, author_name: str, text: str) -> Dict[str, Any]:
    return add_message(
        ticket_id=ticket_id,
        sender_type="internal_note",
        sender_name=author_name,
        text=text,
        is_internal=1
    )

def get_all_tickets(status_filter: Optional[str] = None, 
                    assigned_filter: Optional[str] = None,
                    category_filter: Optional[str] = None,
                    sla_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT t.*, 
               (SELECT text FROM messages WHERE ticket_id = t.id ORDER BY id DESC LIMIT 1) as last_message,
               (SELECT created_at FROM messages WHERE ticket_id = t.id ORDER BY id DESC LIMIT 1) as last_message_time,
               (SELECT COUNT(*) FROM messages WHERE ticket_id = t.id) as message_count
        FROM tickets t
        WHERE 1=1
    """
    params = []
    if status_filter and status_filter != 'all':
        if status_filter in ('closed', 'resolved'):
            query += " AND t.status IN ('closed', 'resolved')"
        else:
            query += " AND t.status = ?"
            params.append(status_filter)
            
    if assigned_filter:
        if assigned_filter == 'unassigned':
            query += " AND (t.assigned_to IS NULL OR t.assigned_to = '')"
        elif assigned_filter != 'all':
            query += " AND t.assigned_to = ?"
            params.append(assigned_filter)

    if category_filter and category_filter != 'all':
        query += " AND t.category = ?"
        params.append(category_filter)

    if sla_filter == 'risk':
        query += " AND (t.sla_breached = 1 OR t.sla_warning_sent = 1)"
        
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

def get_stats(agent_username: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()

    # 1. Global totals by status
    cursor.execute("SELECT COUNT(*) FROM tickets")
    total_all = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")
    open_all = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'in_progress'")
    prog_all = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('resolved', 'closed')")
    closed_all = cursor.fetchone()[0]

    # 2. Unassigned totals by status
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE (assigned_to IS NULL OR assigned_to = '')")
    unassigned_total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open' AND (assigned_to IS NULL OR assigned_to = '')")
    unassigned_open = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'in_progress' AND (assigned_to IS NULL OR assigned_to = '')")
    unassigned_prog = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('resolved', 'closed') AND (assigned_to IS NULL OR assigned_to = '')")
    unassigned_closed = cursor.fetchone()[0]

    # 3. Mine totals by status
    mine_total = 0
    mine_open = 0
    mine_prog = 0
    mine_closed = 0
    if agent_username:
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE assigned_to = ?", (agent_username,))
        mine_total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open' AND assigned_to = ?", (agent_username,))
        mine_open = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'in_progress' AND assigned_to = ?", (agent_username,))
        mine_prog = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('resolved', 'closed') AND assigned_to = ?", (agent_username,))
        mine_closed = cursor.fetchone()[0]

    # 4. SLA Risk count (breached or in warning among open tickets)
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('open', 'in_progress') AND (sla_breached = 1 OR sla_warning_sent = 1)")
    sla_risks = cursor.fetchone()[0]

    # 5. CSAT average rating
    cursor.execute("SELECT AVG(rating), COUNT(rating) FROM tickets WHERE rating IS NOT NULL")
    r_row = cursor.fetchone()
    avg_rating = round(r_row[0], 1) if (r_row and r_row[0] is not None) else None
    rated_count = r_row[1] if r_row else 0

    # 6. Categories breakdown
    cursor.execute("SELECT category, COUNT(*) FROM tickets GROUP BY category")
    cat_counts = {r[0] or "General": r[1] for r in cursor.fetchall()}

    conn.close()
    return {
        "global": {
            "all": total_all,
            "open": open_all,
            "in_progress": prog_all,
            "closed": closed_all
        },
        "unassigned": {
            "all": unassigned_total,
            "open": unassigned_open,
            "in_progress": unassigned_prog,
            "closed": unassigned_closed
        },
        "mine": {
            "all": mine_total,
            "open": mine_open,
            "in_progress": mine_prog,
            "closed": mine_closed
        },
        "open": open_all,
        "in_progress": prog_all,
        "closed": closed_all,
        "total": total_all,
        "unassigned": unassigned_total,
        "assigned_to_me": mine_total,
        "sla_risks": sla_risks,
        "avg_rating": avg_rating,
        "rated_count": rated_count,
        "categories": cat_counts
    }

# --- SLA Escalation Background Monitor Helpers ---
def get_tickets_for_sla_check() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tickets 
        WHERE status IN ('open', 'in_progress') AND sla_deadline IS NOT NULL
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def mark_sla_warning_sent(ticket_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET sla_warning_sent = 1 WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()

def mark_sla_breach_sent(ticket_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET sla_breached = 1, sla_breach_sent = 1 WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()

# --- Canned Responses Database Functions ---
def init_default_canned_responses():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM canned_responses")
    count = cursor.fetchone()[0]
    
    defaults = [
        ("🔄 Restart Device", "Please restart your computer or router and check again. Let us know if the issue persists.", "Hardware"),
        ("🌐 Check Network Cable", "Please ensure your network cable is firmly plugged into your PC and the link LED is active.", "Network"),
        ("📸 Request Screenshot", "Please send a screenshot or photo of the error message so we can investigate immediately.", "General"),
        ("⚙️ Investigating Issue", "Your ticket has been received and our IT support team is actively investigating it.", "General"),
        ("📞 AnyDesk Remote Session", "Please launch AnyDesk and provide your 9-digit address code so our engineer can connect remotely.", "Software"),
        ("🔑 Password Reset Complete", "Your password has been reset. Please log in using the temporary credentials and update it immediately.", "Email & Accounts"),
        ("✅ Resolved & Confirm", "The issue has been resolved. Please test now and confirm if everything is working normally.", "General"),
    ]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # If empty or if existing defaults contain Arabic, reseed with clean English defaults
    cursor.execute("SELECT id, title, text FROM canned_responses")
    rows = cursor.fetchall()
    has_arabic = any(re.search(r'[\u0600-\u06FF]', r[1] + r[2]) for r in rows) if rows else False

    if count == 0 or has_arabic:
        cursor.execute("DELETE FROM canned_responses WHERE id IN (SELECT id FROM canned_responses)")
        for title, text, cat in defaults:
            cursor.execute("INSERT INTO canned_responses (title, text, category, created_at) VALUES (?, ?, ?, ?)",
                           (title, text, cat, now))
        conn.commit()
    conn.close()

def get_canned_responses() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM canned_responses ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def create_canned_response(title: str, text: str, category: str = "General") -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO canned_responses (title, text, category, created_at) VALUES (?, ?, ?, ?)",
                   (title.strip(), text.strip(), (category or "General").strip(), now))
    conn.commit()
    item_id = cursor.lastrowid
    cursor.execute("SELECT * FROM canned_responses WHERE id = ?", (item_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

def delete_canned_response(item_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM canned_responses WHERE id = ?", (item_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

# --- Knowledge Base / FAQ Articles Functions ---
def init_default_faqs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM faq_articles")
    count = cursor.fetchone()[0]

    defaults = [
        (
            "wifi, wireless, network, internet, connection, access",
            "How to connect to the corporate Wi-Fi network",
            "The official staff Wi-Fi network is: Company-Staff.\nPassword: Welcome@2026.\nIf you experience disconnections, toggle Wi-Fi off and on, or restart your network adapter."
        ),
        (
            "printer, print, paper, toner, network printer, spooler",
            "How to connect to department network printers",
            "To connect to a network printer:\n1. Press Windows + R.\n2. Type \\\\print-server and press Enter.\n3. Double-click your department printer to install drivers automatically.\nIf printing is stuck, ensure the tray has paper and toner is sufficient."
        ),
        (
            "password, reset, forgot, locked, account, login, credentials",
            "Password reset and locked account unlocking",
            "If your account is locked due to multiple incorrect attempts, the system unlocks it automatically after 5 minutes.\nIf you forgot your password completely, reply with your username and an IT specialist will reset it for you immediately."
        ),
        (
            "anydesk, remote, screen share, assistance, connect",
            "How to download and run AnyDesk for remote IT support",
            "Please open your browser, visit https://anydesk.com, and download the free client.\nOnce opened, provide your 9-digit address code to the technician so they can connect securely to your PC."
        ),
        (
            "outlook, email, mail, inbox, send, receive, sync",
            "Troubleshooting Microsoft Outlook or email delivery issues",
            "1. Ensure your internet connection is active and Outlook status shows 'Connected'.\n2. Click 'Send / Receive' > 'Send/Receive All Folders'.\n3. If prompted for password, enter your domain credentials and ensure Caps Lock is off."
        )
    ]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT id, question, answer FROM faq_articles")
    rows = cursor.fetchall()
    has_arabic = any(re.search(r'[\u0600-\u06FF]', r[1] + r[2]) for r in rows) if rows else False

    if count == 0 or has_arabic:
        cursor.execute("DELETE FROM faq_articles WHERE id IN (SELECT id FROM faq_articles)")
        for kw, q, a in defaults:
            cursor.execute("INSERT INTO faq_articles (keywords, question, answer, is_active, helpful_count, created_at) VALUES (?, ?, ?, 1, 0, ?)",
                           (kw, q, a, now))
        conn.commit()
    conn.close()

def get_all_faqs() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faq_articles ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_faq(faq_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faq_articles WHERE id = ?", (faq_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_faq(keywords: str, question: str, answer: str) -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO faq_articles (keywords, question, answer, is_active, helpful_count, created_at) VALUES (?, ?, ?, 1, 0, ?)",
                   (keywords.strip(), question.strip(), answer.strip(), now))
    conn.commit()
    fid = cursor.lastrowid
    cursor.execute("SELECT * FROM faq_articles WHERE id = ?", (fid,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

def update_faq(faq_id: int, keywords: str, question: str, answer: str, is_active: int = 1) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE faq_articles SET keywords = ?, question = ?, answer = ?, is_active = ? WHERE id = ?",
                   (keywords.strip(), question.strip(), answer.strip(), is_active, faq_id))
    conn.commit()
    cursor.execute("SELECT * FROM faq_articles WHERE id = ?", (faq_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_faq(faq_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM faq_articles WHERE id = ?", (faq_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def increment_faq_helpful(faq_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE faq_articles SET helpful_count = helpful_count + 1 WHERE id = ?", (faq_id,))
    conn.commit()
    conn.close()

def match_faq(user_text: str) -> Optional[Dict[str, Any]]:
    """Matches user query against active FAQ keywords and returns best matching FAQ if score >= 1."""
    if not user_text or len(user_text.strip()) < 3:
        return None
    
    clean_text = user_text.lower().strip()
    faqs = get_all_faqs()
    
    best_match = None
    best_score = 0
    
    for f in faqs:
        if not f.get("is_active"):
            continue
        keywords = [k.strip().lower() for k in f.get("keywords", "").split(",") if k.strip()]
        score = 0
        for kw in keywords:
            if kw and kw in clean_text:
                score += len(kw)  # longer keyword match gets higher weight
        if score > best_score:
            best_score = score
            best_match = f
            
    return best_match if best_score > 0 else None

def get_analytics_report(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    
    where_clauses = []
    params = []
    
    if start_date:
        where_clauses.append("DATE(created_at) >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("DATE(created_at) <= ?")
        params.append(end_date)
        
    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    
    cursor.execute(f"SELECT * FROM tickets {where_sql} ORDER BY created_at DESC", params)
    tickets = [dict(t) for t in cursor.fetchall()]
    
    total = len(tickets)
    closed = [t for t in tickets if t["status"] in ("closed", "resolved")]
    open_tickets = [t for t in tickets if t["status"] == "open"]
    in_prog = [t for t in tickets if t["status"] == "in_progress"]
    
    # SLA calculations
    now_dt = datetime.now()
    sla_breached_count = 0
    for t in tickets:
        if t["status"] in ("closed", "resolved"):
            if t.get("sla_breached"):
                sla_breached_count += 1
        elif t.get("sla_deadline"):
            try:
                dl = datetime.strptime(t["sla_deadline"], "%Y-%m-%d %H:%M:%S")
                if now_dt > dl:
                    sla_breached_count += 1
            except Exception:
                pass
                
    closed_count = len(closed)
    sla_met_count = max(0, closed_count - len([t for t in closed if t.get("sla_breached")]))
    sla_compliance_rate = round((sla_met_count / closed_count * 100), 1) if closed_count > 0 else 100.0

    # Resolution times
    resolution_times = []
    for t in closed:
        if t.get("created_at") and t.get("closed_at"):
            try:
                c_dt = datetime.strptime(t["created_at"], "%Y-%m-%d %H:%M:%S")
                cl_dt = datetime.strptime(t["closed_at"], "%Y-%m-%d %H:%M:%S")
                diff_mins = (cl_dt - c_dt).total_seconds() / 60.0
                if diff_mins >= 0:
                    resolution_times.append(diff_mins)
            except Exception:
                pass
    avg_resolution_mins = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0.0

    # First response times
    response_times = []
    for t in tickets:
        if t.get("created_at") and t.get("first_response_at"):
            try:
                c_dt = datetime.strptime(t["created_at"], "%Y-%m-%d %H:%M:%S")
                r_dt = datetime.strptime(t["first_response_at"], "%Y-%m-%d %H:%M:%S")
                diff_mins = (r_dt - c_dt).total_seconds() / 60.0
                if diff_mins >= 0:
                    response_times.append(diff_mins)
            except Exception:
                pass
    avg_first_response_mins = round(sum(response_times) / len(response_times), 1) if response_times else 0.0

    # Technician breakdown (Team Leaderboard)
    cursor.execute("SELECT username FROM users")
    all_users = [r["username"] for r in cursor.fetchall()]
    
    tech_stats = {}
    for u in all_users:
        tech_stats[u] = {
            "username": u,
            "total_handled": 0,
            "resolved": 0,
            "sla_breached": 0,
            "resolution_times": [],
            "ratings": []
        }
    tech_stats["Unassigned"] = {
        "username": "Unassigned",
        "total_handled": 0,
        "resolved": 0,
        "sla_breached": 0,
        "resolution_times": [],
        "ratings": []
    }

    for t in tickets:
        assignee = t.get("assigned_to") or "Unassigned"
        if assignee not in tech_stats:
            tech_stats[assignee] = {
                "username": assignee,
                "total_handled": 0,
                "resolved": 0,
                "sla_breached": 0,
                "resolution_times": [],
                "ratings": []
            }
        tech_stats[assignee]["total_handled"] += 1
        if t["status"] in ("closed", "resolved"):
            tech_stats[assignee]["resolved"] += 1
            if t.get("sla_breached"):
                tech_stats[assignee]["sla_breached"] += 1
            if t.get("created_at") and t.get("closed_at"):
                try:
                    c_dt = datetime.strptime(t["created_at"], "%Y-%m-%d %H:%M:%S")
                    cl_dt = datetime.strptime(t["closed_at"], "%Y-%m-%d %H:%M:%S")
                    diff = (cl_dt - c_dt).total_seconds() / 60.0
                    if diff >= 0:
                        tech_stats[assignee]["resolution_times"].append(diff)
                except Exception:
                    pass
            if t.get("rating") is not None:
                try:
                    tech_stats[assignee]["ratings"].append(int(t["rating"]))
                except Exception:
                    pass

    technicians = []
    for u, data in tech_stats.items():
        res_count = data["resolved"]
        sla_met = max(0, res_count - data["sla_breached"])
        sla_pct = round((sla_met / res_count * 100), 1) if res_count > 0 else 100.0
        avg_res = round(sum(data["resolution_times"]) / len(data["resolution_times"]), 1) if data["resolution_times"] else 0.0
        tech_ratings = data["ratings"]
        avg_r = round(sum(tech_ratings) / len(tech_ratings), 1) if tech_ratings else None
        technicians.append({
            "username": u,
            "total_handled": data["total_handled"],
            "resolved": res_count,
            "sla_compliance_rate": sla_pct,
            "avg_resolution_mins": avg_res,
            "avg_rating": avg_r,
            "rated_count": len(tech_ratings)
        })
    # Sort technicians by resolved count descending
    technicians.sort(key=lambda x: x["resolved"], reverse=True)

    # Daily trends (date -> created, resolved)
    trends_dict = {}
    for t in tickets:
        d = t["created_at"][:10] if t.get("created_at") else "Unknown"
        if d not in trends_dict:
            trends_dict[d] = {"date": d, "created": 0, "resolved": 0}
        trends_dict[d]["created"] += 1
        if t["status"] in ("closed", "resolved"):
            trends_dict[d]["resolved"] += 1
            
    daily_trends = sorted(trends_dict.values(), key=lambda x: x["date"])

    # Category breakdown
    cat_stats = {}
    for t in tickets:
        cat = t.get("category") or "General"
        if cat not in cat_stats:
            cat_stats[cat] = {"category": cat, "total": 0, "resolved": 0}
        cat_stats[cat]["total"] += 1
        if t["status"] in ("closed", "resolved"):
            cat_stats[cat]["resolved"] += 1
    categories_breakdown = sorted(cat_stats.values(), key=lambda x: x["total"], reverse=True)

    # Overall CSAT
    all_ratings = [int(t["rating"]) for t in tickets if t.get("rating") is not None]
    overall_avg_rating = round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else None

    conn.close()
    return {
        "summary": {
            "total_tickets": total,
            "closed_tickets": closed_count,
            "open_tickets": len(open_tickets),
            "in_progress_tickets": len(in_prog),
            "sla_breached_count": sla_breached_count,
            "sla_compliance_rate": sla_compliance_rate,
            "avg_resolution_mins": avg_resolution_mins,
            "avg_first_response_mins": avg_first_response_mins,
            "avg_rating": overall_avg_rating,
            "rated_count": len(all_ratings)
        },
        "technicians": technicians,
        "daily_trends": daily_trends,
        "categories": categories_breakdown,
        "tickets": tickets
    }

