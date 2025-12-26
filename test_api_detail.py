import requests
import json

response = requests.get('http://localhost:8080/api/trading-log?since_id=0')
data = response.json()

print(f"=== API 응답 ===")
print(f"매수: {len(data.get('buys', []))}건")
print(f"매도: {len(data.get('sells', []))}건")
print(f"\n=== 통계 ===")
stats = data.get('stats', {})
print(json.dumps(stats, indent=2, ensure_ascii=False))

print(f"\n=== 매수 샘플 (최신 3건) ===")
for buy in data.get('buys', [])[:3]:
    print(f"ID: {buy['id']}, 시간: {buy['time']}, 종목: {buy.get('stk_nm', 'N/A')}, 수량: {buy['qty']}")

print(f"\n=== 매도 샘플 (최신 3건) ===")
for sell in data.get('sells', [])[:3]:
    print(f"ID: {sell['id']}, 시간: {sell['time']}, 종목: {sell.get('stk_nm', 'N/A')}, 수익률: {sell.get('profit_rate', 0)}%")
