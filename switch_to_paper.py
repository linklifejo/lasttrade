import sqlite3
import os

db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Paper Trading 모드로 전환 (키움 모의투자)
cursor.execute("UPDATE settings SET value = 'false' WHERE key = 'use_mock_server'")
cursor.execute("UPDATE settings SET value = 'true' WHERE key = 'is_paper_trading'")

conn.commit()
conn.close()

print("✅ Paper Trading 모드로 전환 완료! (키움 모의투자)")
print("📌 use_mock_server = false")
print("📌 is_paper_trading = true")
print("🚀 봇을 시작하세요: python start.py")
