import sqlite3
import os
import datetime

def check():
    db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    
    # Check total counts by mode
    print("--- Mode distribution ---")
    cursor = conn.execute('SELECT mode, COUNT(*) as cnt FROM trades GROUP BY mode')
    for row in cursor.fetchall():
        print(f"Mode: {row['mode']}, Count: {row['cnt']}")
    
    # Check today's trades
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    print(f"\n--- Today's trades ({today}) ---")
    cursor = conn.execute('SELECT mode, type, COUNT(*) as cnt FROM trades WHERE timestamp LIKE ? GROUP BY mode, type', (f"{today}%",))
    for row in cursor.fetchall():
        print(f"Mode: {row['mode']}, Type: {row['type']}, Count: {row['cnt']}")

if __name__ == "__main__":
    check()
