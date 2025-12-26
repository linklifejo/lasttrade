
import sqlite3
import os

DB_FILE = 'trading.db'

def check_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    
    print("--- Settings Table ---")
    rows = conn.execute("SELECT key, value FROM settings WHERE key IN ('use_mock_server', 'is_paper_trading', 'process_name')").fetchall()
    for row in rows:
        print(f"{row['key']}: {row['value']}")
        
    print("\n--- Trades Table (Modes) ---")
    rows = conn.execute("SELECT DISTINCT mode FROM trades").fetchall()
    for row in rows:
        print(f"Mode in DB: {row['mode']}")
        
    print("\n--- Last 5 Trades ---")
    rows = conn.execute("SELECT timestamp, type, code, name, mode FROM trades ORDER BY id DESC LIMIT 5").fetchall()
    for row in rows:
        print(f"[{row['mode']}] {row['timestamp']} {row['type']} {row['name']}")
        
    conn.close()

if __name__ == "__main__":
    check_db()
