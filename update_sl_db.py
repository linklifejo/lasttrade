
import sqlite3
import os

DB_PATH = 'c:/lasttrade/trading.db'

def update_sl():
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Force update 'stop_loss_rate' to -3
    cursor.execute("UPDATE settings SET value = '-3' WHERE key = 'stop_loss_rate'")
    # Also insert 'sl_rate' just in case code uses that key
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sl_rate', '-3')")
    
    conn.commit()
    print("✅ Stop Loss Rate updated to -3% (both keys).")
    conn.close()

if __name__ == "__main__":
    update_sl()
