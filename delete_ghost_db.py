
import sqlite3
import os

DB_PATH = 'c:/lasttrade/trading.db'

def exorcise_ghost():
    print("👻 Exorcising Ghost Stock 'SAT (060540)' from DB...")
    
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check if it exists
    cursor.execute("SELECT * FROM mock_stocks WHERE code = '060540'")
    row = cursor.fetchone()
    if row:
        print(f"👻 Found Ghost: {row}")
        # 2. Delete it
        cursor.execute("DELETE FROM mock_stocks WHERE code = '060540'")
        print("⚔️ Ghost Deleted.")
    else:
        print("❓ Ghost not found in DB. Maybe it was only in memory?")

    conn.commit()
    conn.close()
    print("✅ Exorcism Complete.")

if __name__ == "__main__":
    exorcise_ghost()
