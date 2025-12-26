import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def dump_trades():
    if not os.path.exists(DB_FILE):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Trades Table Content ---")
    cursor.execute("SELECT * FROM trades LIMIT 20")
    rows = cursor.fetchall()
    
    if not rows:
        print("No trades found in DB")
    else:
        for row in rows:
            print(dict(row))
            
    conn.close()

if __name__ == "__main__":
    dump_trades()
