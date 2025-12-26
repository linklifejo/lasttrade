import requests
import json

url = 'http://localhost:8080/api/settings'
headers = {'Content-Type': 'application/json'}
data = {
    'trading_mode': 'MOCK',
    'use_mock_server': True,
    'is_paper_trading': False,
    'process_name': '모의'
}

try:
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
