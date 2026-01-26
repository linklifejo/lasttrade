import sqlite3
import os

DB_FILE = 'trading.db'

def check_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    
    print("--- mock_account ---")
    rows = conn.execute("SELECT * FROM mock_account").fetchall()
    for row in rows:
        print(dict(row))
        
    print("\n--- mock_holdings (qty > 0) ---")
    rows = conn.execute("SELECT * FROM mock_holdings WHERE qty > 0").fetchall()
    for row in rows:
        print(dict(row))
        
    print("\n--- mock_prices for holdings ---")
    rows = conn.execute("SELECT * FROM mock_prices WHERE code IN (SELECT code FROM mock_holdings WHERE qty > 0)").fetchall()
    for row in rows:
        print(dict(row))
    
    conn.close()

if __name__ == "__main__":
    check_db()
