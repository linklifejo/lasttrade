import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# 저장된 토큰 삭제
cursor.execute("DELETE FROM settings WHERE key = 'access_token'")
cursor.execute("DELETE FROM settings WHERE key = 'token_issued_at'")

conn.commit()
print("✅ 저장된 토큰을 삭제했습니다.")
print("🔄 봇을 재시작하면 새로운 토큰을 발급받습니다.")

conn.close()
