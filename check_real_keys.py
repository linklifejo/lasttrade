import sqlite3

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# Real API 키 조회
cursor.execute("SELECT key, value FROM settings WHERE key IN ('real_app_key', 'real_app_secret')")
rows = cursor.fetchall()

print("=" * 60)
print("Real API 키 확인")
print("=" * 60)

for key, value in rows:
    if value:
        print(f"{key}: {value[:20]}... (길이: {len(value)})")
    else:
        print(f"{key}: (없음)")

conn.close()
