
import sqlite3
import os

DB_PATH = 'c:/lasttrade/trading.db'

def find_culprit():
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔍 Searching for values like -1...")
    
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    
    found = False
    for key, val in rows:
        if str(val).strip() == '-1' or str(val).strip() == '-1.0':
            print(f"👉 FOUND CULPRIT! [{key}] -> {val}")
            found = True
            
        # SL 관련 키는 무조건 출력
        if 'sl' in key.lower() or 'stop' in key.lower():
            print(f"ℹ️ [Check] {key} = {val}")

    if not found:
        print("✅ No settings with value -1 found.")

    conn.close()

if __name__ == "__main__":
    find_culprit()
