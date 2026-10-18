"""
Reset Database to Clean State for New Client / Testing.
Copies 'helpdesk_clean.db' over 'helpdesk.db', wiping previous test tickets
and restoring a factory-fresh installation ready for a new company.
"""

import os
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLEAN_DB = os.path.join(BASE_DIR, "helpdesk_clean.db")
ACTIVE_DB = os.path.join(BASE_DIR, "helpdesk.db")

def reset_database():
    if not os.path.exists(CLEAN_DB):
        import create_clean_db
        create_clean_db.generate_clean_database()
        
    shutil.copyfile(CLEAN_DB, ACTIVE_DB)
    print("Database has been reset to factory-fresh clean state successfully!")
    print("Default credentials: username=admin / password=admin123")
    print("Telegram bot token and group ID are cleared, ready for new client setup.")

if __name__ == "__main__":
    reset_database()
