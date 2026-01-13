import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT updated_at FROM system_status WHERE api_mode = 'REAL'")
row = cursor.fetchone()
print(f"Updated at: {row[0] if row else 'None'}")
conn.close()
