import sqlite3
import os

db_path = 'trading.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings WHERE key IN ('use_mock_server', 'is_paper_trading', 'trading_mode');")
    rows = cursor.fetchall()
    print("--- Current Settings in DB ---")
    for row in rows:
        print(f"{row['key']}: {row['value']}")
    conn.close()
else:
    print("DB file not found")
