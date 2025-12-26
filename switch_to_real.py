import sqlite3
import os

# Real 모드로 전환
db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# is_paper_trading = false (Real 모드)
cursor.execute("UPDATE settings SET value = 'false' WHERE key = 'is_paper_trading'")

# use_mock_server = false (실제 API 사용)
cursor.execute("UPDATE settings SET value = 'false' WHERE key = 'use_mock_server'")

conn.commit()
conn.close()

print("✅ Real 모드로 전환 완료!")
print("📌 is_paper_trading = false")
print("📌 use_mock_server = false")
print("🚀 봇을 재시작하세요: python start.py")
