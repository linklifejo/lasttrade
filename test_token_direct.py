import requests
import json

url = 'https://mockapi.kiwoom.com/oauth2/token'
headers = {'Content-Type': 'application/json;charset=UTF-8'}
data = {
    'grant_type': 'client_credentials',
    'appkey': 'I8zHt-F_c9LPHCab9S0IsaPAxW_2N4Wx0AXUKZ9fX0I',
    'secretkey': 'lQcU0XYj0SzVxAf8P-f5Uv4wxxywGZbPZq-LMrt2_MQ'
}

try:
    print(f"Requesting token from: {url}")
    r = requests.post(url, headers=headers, json=data, timeout=10)
    print(f"Status Code: {r.status_code}")
    print(f"Response Headers: {dict(r.headers)}")
    print(f"Response Body: {r.text}")
    
    if r.status_code == 200:
        result = r.json()
        token = result.get('token') or result.get('access_token')
        print(f"\nToken extracted: {token[:20] if token else 'None'}...")
    else:
        print(f"\nError: HTTP {r.status_code}")
except Exception as e:
    print(f"Exception: {e}")
