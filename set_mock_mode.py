import sqlite3
import os

db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# MOCK 모드로 변경
cursor.execute("UPDATE settings SET value = 'true' WHERE key = 'use_mock_server'")
cursor.execute("UPDATE settings SET value = 'MOCK' WHERE key = 'trading_mode'")

conn.commit()
conn.close()

print("✅ MOCK 모드로 변경 완료")
