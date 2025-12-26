import requests
import json
import time

# 1. Restore to REAL mode
url = 'http://localhost:8080/api/settings'
headers = {'Content-Type': 'application/json'}
data = {
    'trading_mode': 'REAL',
    'use_mock_server': False,
    'is_paper_trading': False,
    'process_name': '실전'
}

try:
    print("Switching back to REAL mode...")
    response = requests.post(url, headers=headers, json=data)
    print(f"Setting Update Response: {response.text}")
    
    # Wait for bot to detect change
    time.sleep(3)
    
    # 2. Check Status
    print("Checking Status...")
    resp = requests.get('http://localhost:8080/api/status')
    status = resp.json()
    print(f"Current Mode: {status.get('summary', {}).get('api_mode')}")
    holdings = status.get('holdings', [])
    print(f"Holdings Count: {len(holdings)}")
    if holdings:
        print(f"First Holding: {holdings[0].get('stk_nm')}")

except Exception as e:
    print(f"Error: {e}")
