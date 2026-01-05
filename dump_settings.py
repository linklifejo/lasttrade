
import sqlite3
import os

DB_PATH = 'c:/lasttrade/trading.db'

def dump_settings():
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("📋 Current Settings in DB:")
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    
    if rows:
        for key, val in rows:
            print(f"  - {key}: {val}")
    else:
        print("  (Table is empty)")

    conn.close()

if __name__ == "__main__":
    dump_settings()
