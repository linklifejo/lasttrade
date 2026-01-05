import sqlite3
import time

conn = sqlite3.connect('c:/lasttrade/trading.db')
cursor = conn.cursor()

print("=" * 60)
print("익절 수익률 모니터링")
print("=" * 60)

# 현재 값
cursor.execute("SELECT value FROM settings WHERE key='take_profit_rate'")
current = cursor.fetchone()[0]
print(f"\n현재 DB 값: {current}")

print("\n사용자님이 3으로 변경하고 저장 버튼을 누르면...")
print("10초마다 DB를 체크합니다. (Ctrl+C로 중단)")

try:
    while True:
        time.sleep(10)
        cursor.execute("SELECT value FROM settings WHERE key='take_profit_rate'")
        new_value = cursor.fetchone()[0]
        
        if str(new_value) != str(current):
            print(f"\n✅ 변경 감지! {current} → {new_value}")
            print(f"   시간: {time.strftime('%H:%M:%S')}")
            current = new_value
        else:
            print(f"   {time.strftime('%H:%M:%S')} - 아직 {current} (변경 없음)")
            
except KeyboardInterrupt:
    print("\n\n모니터링 종료")
finally:
    conn.close()
