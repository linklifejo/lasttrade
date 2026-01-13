import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT value FROM settings WHERE key='use_mock_server'")
row = cursor.fetchone()
print(f"use_mock_server: {row[0] if row else 'None'}")
conn.close()
