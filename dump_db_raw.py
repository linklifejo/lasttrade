import sqlite3
import os

db_path = 'c:\\lasttrade\\trading.db'
if not os.path.exists(db_path):
    print(f"❌ DB 파일이 발견되지 않았습니다: {db_path}")
    exit()

print(f"📂 DB 파일 연결: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("-" * 60)
print("🔍 'settings' 테이블 내 인증 정보(Key/Secret) 조회 결과")
print("-" * 60)

# 인증 관련 키워드로 조회
cursor.execute("SELECT key, value FROM settings WHERE key IN ('real_app_key', 'real_app_secret', 'paper_app_key', 'paper_app_secret', 'my_account', 'telegram_chat_id', 'telegram_token')")
rows = cursor.fetchall()

if not rows:
    print("⚠️ DB에 인증 정보가 하나도 없습니다! (Empty)")
else:
    for key, value in rows:
        # 보안을 위해 앞뒤 일부만 보여줌 (길이가 짧으면 그대로)
        if value and len(str(value)) > 10:
            masked = value[:5] + "..." + value[-5:]
        else:
            masked = value
        print(f"✅ {key.ljust(20)} : {masked}")

print("-" * 60)
conn.close()
