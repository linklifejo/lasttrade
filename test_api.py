import requests

response = requests.get('http://localhost:8080/api/trading-log?since_id=0')
data = response.json()

print(f"매수: {len(data['buys'])}건")
print(f"매도: {len(data['sells'])}건")
print(f"통계: {data['stats']}")
