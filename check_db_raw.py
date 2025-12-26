import sqlite3
import datetime

def check():
    conn = sqlite3.connect('trading.db')
    conn.row_factory = sqlite3.Row
    
    # Check total counts by mode with raw values
    print("--- Mode raw values ---")
    cursor = conn.execute('SELECT DISTINCT mode FROM trades')
    for row in cursor.fetchall():
        print(f"Mode (raw): {repr(row['mode'])}")
    
    # Check today's trades with raw types
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    print(f"\n--- Today's trades types ({today}) ---")
    cursor = conn.execute('SELECT DISTINCT type FROM trades WHERE timestamp LIKE ?', (f"{today}%",))
    for row in cursor.fetchall():
        print(f"Type (raw): {repr(row['type'])}")

if __name__ == "__main__":
    check()
