import sqlite3
import time

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

# 토큰 발급 시간 조회
cursor.execute("SELECT key, value FROM settings WHERE key LIKE '%token_time%'")
rows = cursor.fetchall()

print("=" * 60)
print("토큰 발급 시도 기록")
print("=" * 60)

if rows:
    for key, value in rows:
        if value:
            try:
                token_time = float(value)
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(token_time))
                hours_ago = (time.time() - token_time) / 3600
                print(f"{key}:")
                print(f"  발급 시간: {time_str}")
                print(f"  경과 시간: {hours_ago:.1f}시간 전")
                print()
            except:
                print(f"{key}: 파싱 실패")
        else:
            print(f"{key}: 없음")
else:
    print("토큰 발급 기록 없음")

conn.close()

print("=" * 60)
print("📌 1시간 이내 발급 기록이 1개만 있으면 안전합니다")
print("=" * 60)
