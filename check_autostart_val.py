import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT key, value FROM settings WHERE key='auto_start'")
row = cursor.fetchone()
print(f"auto_start: {row[1] if row else 'None'}")
conn.close()
