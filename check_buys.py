import sqlite3
import os

def check_recent_buys():
    conn = sqlite3.connect('trading.db', timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, code, name, type FROM trades WHERE type='buy' ORDER BY timestamp DESC LIMIT 20")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()

if __name__ == "__main__":
    check_recent_buys()
