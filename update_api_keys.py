import sqlite3

# 여기에 새로 발급받은 키를 입력하세요
NEW_REAL_APP_KEY = "여기에_실전투자_AppKey_입력"
NEW_REAL_APP_SECRET = "여기에_실전투자_AppSecret_입력"

NEW_PAPER_APP_KEY = "여기에_모의투자_AppKey_입력"
NEW_PAPER_APP_SECRET = "여기에_모의투자_AppSecret_입력"

import os

# DB 업데이트
db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Real API 키 업데이트
cursor.execute("UPDATE settings SET value = ? WHERE key = 'real_app_key'", (NEW_REAL_APP_KEY,))
cursor.execute("UPDATE settings SET value = ? WHERE key = 'real_app_secret'", (NEW_REAL_APP_SECRET,))

# Paper API 키 업데이트
cursor.execute("UPDATE settings SET value = ? WHERE key = 'paper_app_key'", (NEW_PAPER_APP_KEY,))
cursor.execute("UPDATE settings SET value = ? WHERE key = 'paper_app_secret'", (NEW_PAPER_APP_SECRET,))

conn.commit()
conn.close()

print("✅ API 키 업데이트 완료!")
print("🔄 봇을 재시작하세요: python start.py")
