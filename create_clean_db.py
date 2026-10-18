"""
Clean Database Generator for IT Support Helpdesk.
Creates a pristine, production-ready 'helpdesk_clean.db' with:
- 0 tickets
- 0 customer messages
- 0 user profiles
- 0 active sessions
- 1 default admin account (username: admin / password: admin123)
- 7 default English canned response templates
- 5 default English FAQ articles
- Empty Telegram Token & Group ID (prompts client to configure their own bot upon first launch)
"""

import sqlite3
import os
import hashlib
from datetime import datetime

TARGET_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpdesk_clean.db")

def hash_password(password: str, salt: str = "helpdesk_salt_2026") -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def generate_clean_database():
    if os.path.exists(TARGET_DB):
        os.remove(TARGET_DB)
        print(f"Removed previous {TARGET_DB}")

    conn = sqlite3.connect(TARGET_DB)
    cursor = conn.cursor()

    # 1. Settings Table
    cursor.execute("""
    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    cursor.execute("INSERT INTO settings (key, value) VALUES ('telegram_bot_token', '')")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('it_alert_group_id', '')")

    # 2. Users Table
    cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT DEFAULT 'admin',
        created_at TEXT
    )
    """)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
        ("admin", hash_password("admin123"), now)
    )

    # 3. Tickets Table
    cursor.execute("""
    CREATE TABLE tickets (
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
        closed_at TEXT,
        assigned_to TEXT DEFAULT NULL,
        assigned_at TEXT DEFAULT NULL,
        priority TEXT DEFAULT 'medium',
        category TEXT DEFAULT 'General',
        first_response_at TEXT DEFAULT NULL,
        sla_deadline TEXT DEFAULT NULL,
        sla_breached INTEGER DEFAULT 0,
        sla_warning_sent INTEGER DEFAULT 0,
        sla_breach_sent INTEGER DEFAULT 0,
        rating INTEGER DEFAULT NULL,
        rating_comment TEXT DEFAULT NULL,
        rated_at TEXT DEFAULT NULL,
        last_sender_type TEXT DEFAULT 'user',
        sla_paused INTEGER DEFAULT 0,
        sla_paused_at TEXT DEFAULT NULL
    )
    """)
    cursor.execute("CREATE INDEX idx_tickets_user_status ON tickets(telegram_user_id, status)")

    # 4. Messages Table
    cursor.execute("""
    CREATE TABLE messages (
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
    cursor.execute("CREATE INDEX idx_messages_ticket_id ON messages(ticket_id)")

    # 5. Canned Responses
    cursor.execute("""
    CREATE TABLE canned_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        text TEXT,
        category TEXT DEFAULT 'General',
        created_at TEXT
    )
    """)
    canned_defaults = [
        ("🔄 Restart Device", "Please restart your computer or router and check again. Let us know if the issue persists.", "Hardware"),
        ("🌐 Check Network Cable", "Please ensure your network cable is firmly plugged into your PC and the link LED is active.", "Network"),
        ("📸 Request Screenshot", "Please send a screenshot or photo of the error message so we can investigate immediately.", "General"),
        ("⚙️ Investigating Issue", "Your ticket has been received and our IT support team is actively investigating it.", "General"),
        ("📞 AnyDesk Remote Session", "Please launch AnyDesk and provide your 9-digit address code so our engineer can connect remotely.", "Software"),
        ("🔑 Password Reset Complete", "Your password has been reset. Please log in using the temporary credentials and update it immediately.", "Email & Accounts"),
        ("✅ Resolved & Confirm", "The issue has been resolved. Please test now and confirm if everything is working normally.", "General"),
    ]
    for title, text, cat in canned_defaults:
        cursor.execute("INSERT INTO canned_responses (title, text, category, created_at) VALUES (?, ?, ?, ?)",
                       (title, text, cat, now))

    # 6. FAQ Articles
    cursor.execute("""
    CREATE TABLE faq_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keywords TEXT,
        question TEXT,
        answer TEXT,
        is_active INTEGER DEFAULT 1,
        helpful_count INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    faq_defaults = [
        (
            "wifi, wi-fi, network, internet, connection, slow, disconnected",
            "How to connect to the corporate Wi-Fi network",
            "Select 'Corp-Secure-WiFi' from available networks, enter your company username and password, and accept the security certificate when prompted."
        ),
        (
            "printer, print, paper jam, toner, scanning, scan, printer offline",
            "How to connect to department network printers",
            "Open Windows Settings -> Printers & Scanners -> Add Device. Enter \\\\print-server\\IT-Printer-01 or choose your floor printer from the list."
        ),
        (
            "password, reset, forgot password, locked, unlock, account locked",
            "Password reset and locked account unlocking",
            "If your account is locked after failed attempts, wait 15 minutes for auto-unlock or message IT Support here with your Employee ID to reset your password immediately."
        ),
        (
            "anydesk, remote, teamviewer, support, remote control, screen share",
            "How to download and run AnyDesk for remote IT support",
            "Download AnyDesk from https://anydesk.com/download. Run the client and share the 9-digit address number with the IT technician in this chat."
        ),
        (
            "outlook, email, mail, exchange, office 365, mailbox full, cannot send",
            "Troubleshooting Microsoft Outlook or email delivery issues",
            "Restart Microsoft Outlook. If emails are stuck in the Outbox, check your internet cable/Wi-Fi and restart Outlook in Safe Mode by holding CTRL while launching."
        )
    ]
    for kw, q, a in faq_defaults:
        cursor.execute("INSERT INTO faq_articles (keywords, question, answer, is_active, helpful_count, created_at) VALUES (?, ?, ?, 1, 0, ?)",
                       (kw, q, a, now))

    # 7. Sessions Table
    cursor.execute("""
    CREATE TABLE sessions (
        token TEXT PRIMARY KEY,
        username TEXT,
        created_at TEXT,
        expires_at TEXT
    )
    """)

    # 8. User Profiles Table
    cursor.execute("""
    CREATE TABLE user_profiles (
        telegram_user_id INTEGER PRIMARY KEY,
        user_name TEXT,
        username TEXT,
        phone_number TEXT,
        updated_at TEXT
    )
    """)

    conn.commit()
    conn.close()
    print(f"Pristine production database generated successfully at: {TARGET_DB}")

if __name__ == "__main__":
    generate_clean_database()
