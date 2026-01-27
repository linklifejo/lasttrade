import sqlite3
import pandas as pd

def check_samsung():
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    print("--- Holdings for 005930 ---")
    cursor.execute("SELECT * FROM holdings WHERE stock_code='005930'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    print("\n--- Settings (checking for target_stocks) ---")
    cursor.execute("SELECT * FROM settings WHERE key='target_stocks'")
    print(cursor.fetchall())
    
    conn.close()

if __name__ == "__main__":
    check_samsung()
