import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def check_trades():
    if not os.path.exists(DB_FILE):
        print("DB file not found")
        return
        
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        print("--- Mode Frequency in trades table ---")
        cursor.execute("SELECT mode, count(*) FROM trades GROUP BY mode")
        rows = cursor.fetchall()
        for row in rows:
            print(f"Mode: {row[0]}, Count: {row[1]}")
            
        print("\n--- Current Settings Related to Mode ---")
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('trading_mode', 'use_mock_server', 'is_paper_trading')")
        rows = cursor.fetchall()
        for row in rows:
            print(f"Key: {row[0]}, Value: {row[1]}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_trades()
