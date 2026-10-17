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
    
    columns_to_add = [
        ("last_message_id", "INTEGER DEFAULT 0"),
        ("assigned_to", "TEXT DEFAULT NULL"),
        ("assigned_at", "TEXT DEFAULT NULL"),
        ("priority", "TEXT DEFAULT 'medium'"),
        ("first_response_at", "TEXT DEFAULT NULL"),
        ("sla_deadline", "TEXT DEFAULT NULL"),
        ("sla_breached", "INTEGER DEFAULT 0"),
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
    # Ensure default telegram bot token if not set
    default_token = os.getenv("TELEGRAM_BOT_TOKEN", "8825356962:AAH-IwHd43WBNSp34un-RVoQD2w3IjKwlbs").strip()
    cursor.execute("SELECT value FROM settings WHERE key = 'telegram_bot_token'")
    row = cursor.fetchone()
    if not row or not row["value"]:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('telegram_bot_token', ?)", (default_token,))

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

def create_ticket(telegram_chat_id: int, telegram_user_id: int, user_name: str, 
                  username: str, phone_number: str = "", chat_type: str = "private", 
                  chat_title: str = "", subject: str = "", last_message_id: int = 0,
                  priority: str = "medium") -> Dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prio = priority.lower() if priority else "medium"
    if prio not in SLA_HOURS:
        prio = "medium"
    sla_deadline = calculate_sla_deadline(now, prio)
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO tickets (telegram_chat_id, telegram_user_id, user_name, username, 
                             phone_number, chat_type, chat_title, status, subject, 
                             last_message_id, priority, sla_deadline, sla_breached, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, 0, ?, ?)
    """, (telegram_chat_id, telegram_user_id, user_name, username, phone_number, chat_type, 
          chat_title, subject, last_message_id, prio, sla_deadline, now, now))
    
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
        
    if curr["status"] in ('resolved', 'closed') and status not in ('resolved', 'closed'):
        conn.close()
        raise ValueError("Closed tickets cannot be reopened. A new ticket must be created.")

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
        SET status = ?, updated_at = ?, closed_at = COALESCE(?, closed_at),
            sla_breached = CASE WHEN ? = 'closed' THEN ? ELSE sla_breached END
        WHERE id = ?
    """, (status, now, closed_at, status, sla_breached, ticket_id))
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
    
    # If agent reply, record first_response_at if not set
    if sender_type == "agent":
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

def get_all_tickets(status_filter: Optional[str] = None, assigned_filter: Optional[str] = None) -> List[Dict[str, Any]]:
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

def get_stats(agent_username: Optional[str] = None) -> Dict[str, int]:
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
    
    # Unassigned open/in_progress tickets
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('open', 'in_progress') AND (assigned_to IS NULL OR assigned_to = '')")
    unassigned_count = cursor.fetchone()[0]
    
    # Assigned to current user
    assigned_to_me = 0
    if agent_username:
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('open', 'in_progress') AND assigned_to = ?", (agent_username,))
        assigned_to_me = cursor.fetchone()[0]
        
    conn.close()
    return {
        "open": open_count,
        "in_progress": in_progress_count,
        "closed": closed_count,
        "total": total_count,
        "unassigned": unassigned_count,
        "assigned_to_me": assigned_to_me
    }

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
            "resolution_times": []
        }
    tech_stats["Unassigned"] = {
        "username": "Unassigned",
        "total_handled": 0,
        "resolved": 0,
        "sla_breached": 0,
        "resolution_times": []
    }

    for t in tickets:
        assignee = t.get("assigned_to") or "Unassigned"
        if assignee not in tech_stats:
            tech_stats[assignee] = {
                "username": assignee,
                "total_handled": 0,
                "resolved": 0,
                "sla_breached": 0,
                "resolution_times": []
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

    technicians = []
    for u, data in tech_stats.items():
        res_count = data["resolved"]
        sla_met = max(0, res_count - data["sla_breached"])
        sla_pct = round((sla_met / res_count * 100), 1) if res_count > 0 else 100.0
        avg_res = round(sum(data["resolution_times"]) / len(data["resolution_times"]), 1) if data["resolution_times"] else 0.0
        technicians.append({
            "username": u,
            "total_handled": data["total_handled"],
            "resolved": res_count,
            "sla_compliance_rate": sla_pct,
            "avg_resolution_mins": avg_res
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
            "avg_first_response_mins": avg_first_response_mins
        },
        "technicians": technicians,
        "daily_trends": daily_trends,
        "tickets": tickets
    }

