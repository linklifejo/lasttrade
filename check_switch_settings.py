import sqlite3
db_path = r'c:\lasttrade\trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
keys = ['auto_mode_switch_enabled', 'real_mode_switch_time', 'mock_mode_switch_time', 'liquidation_time']
for key in keys:
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    print(f"{key}: {row[0] if row else 'Default'}")
conn.close()
