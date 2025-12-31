import requests
import json
from database_helpers import get_setting

# DB에서 최신 키 가져오기
paper_key = get_setting('paper_app_key')
paper_secret = get_setting('paper_app_secret')

url = 'https://mockapi.kiwoom.com/oauth2/token'
headers = {'Content-Type': 'application/json;charset=UTF-8'}
data = {
    'grant_type': 'client_credentials',
    'appkey': paper_key,
    'secretkey': paper_secret
}

try:
    print(f"Testing with updated keys...")
    print(f"App Key: {paper_key[:20]}...")
    print(f"Requesting token from: {url}")
    
    r = requests.post(url, headers=headers, json=data, timeout=10)
    print(f"\nStatus Code: {r.status_code}")
    print(f"Response Body: {r.text}")
    
    if r.status_code == 200:
        result = r.json()
        token = result.get('token') or result.get('access_token')
        if token:
            print(f"\n✅ SUCCESS! Token received: {token[:30]}...")
        else:
            print(f"\n⚠️ HTTP 200 but no token in response")
            print(f"Response keys: {list(result.keys())}")
    else:
        print(f"\n❌ FAILED: HTTP {r.status_code}")
except Exception as e:
    print(f"❌ Exception: {e}")
