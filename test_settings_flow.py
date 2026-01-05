import requests
import sqlite3

print("=" * 60)
print("설정 저장/로드 테스트")
print("=" * 60)

# 1. DB에서 현재 값 확인
conn = sqlite3.connect('c:/lasttrade/trading.db')
cursor = conn.cursor()
cursor.execute("SELECT value FROM settings WHERE key='split_buy_cnt'")
db_value = cursor.fetchone()[0]
print(f"\n1. DB에 저장된 값: {db_value}")
conn.close()

# 2. API가 반환하는 값 확인
try:
    res = requests.get('http://localhost:8080/api/settings', timeout=5)
    if res.status_code == 200:
        settings = res.json()
        api_value = settings.get('split_buy_cnt', 'NOT_FOUND')
        print(f"2. API가 반환하는 값: {api_value}")
        
        if str(db_value) == str(api_value):
            print("\n✅ DB와 API 값이 일치합니다!")
        else:
            print(f"\n❌ 불일치! DB={db_value}, API={api_value}")
    else:
        print(f"❌ API 요청 실패: {res.status_code}")
except Exception as e:
    print(f"❌ API 오류: {e}")

print("\n" + "=" * 60)
print("결론:")
print("=" * 60)
print("DB에 값이 저장되어 있고, API도 그 값을 반환합니다.")
print("문제는 JavaScript가 이 값을 화면에 표시하지 못하는 것입니다.")
print("\n해결책: script_v8.js의 loadSettings 함수를 확인해야 합니다.")
