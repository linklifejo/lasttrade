import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def check():
    if not os.path.exists(DB_FILE):
        print("DB file not found")
        return
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT mode, type, COUNT(*) as cnt FROM trades GROUP BY mode, type")
        rows = cursor.fetchall()
        print("--- Trades Summary ---")
        for row in rows:
            print(f"Mode: {row['mode']}, Type: {row['type']}, Count: {row['cnt']}")
        
        cursor = conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        print("\n--- Recent 5 Trades ---")
        for row in rows:
            print(dict(row))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check()
