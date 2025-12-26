import sqlite3
import os

DB_FILE = 'trading.db'

def count_modes():
    if not os.path.exists(DB_FILE):
        print("DB not found")
        return
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("--- Mode Counts ---")
    cursor.execute("SELECT mode, type, count(*) FROM trades GROUP BY mode, type")
    rows = cursor.fetchall()
    
    for row in rows:
        print(f"Mode: {row[0]}, Type: {row[1]}, Count: {row[2]}")
            
    conn.close()

if __name__ == "__main__":
    count_modes()
