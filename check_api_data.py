import requests
import json

try:
    res = requests.get("http://localhost:8080/api/trading-log")
    data = res.json()
    print(f"Status: {res.status_code}")
    print(f"Stats: {data.get('stats')}")
    sells = data.get('sells', [])
    buys = data.get('buys', [])
    print(f"Sells: {len(sells)}")
    print(f"Buys: {len(buys)}")
    if buys:
        print(f"First Buy Mode: {buys[0].get('mode')}")
        print(f"First Buy Time: {buys[0].get('time')}")
except Exception as e:
    print(f"Error: {e}")
