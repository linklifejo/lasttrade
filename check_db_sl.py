
import sqlite3
import os

DB_PATH = 'c:/lasttrade/trading.db'

def check_sl():
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT value FROM settings WHERE key = 'sl_rate'")
    row = cursor.fetchone()
    if row:
        print(f"✅ DB stored SL_RATE: {row[0]}")
    else:
        print("❓ SL_RATE not found in DB settings.")

    conn.close()

if __name__ == "__main__":
    check_sl()
