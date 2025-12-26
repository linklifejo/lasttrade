import requests
import json
import time
from database_helpers import get_setting

def test_kis_connection(mode='REAL'):
    if mode == 'REAL':
        app_key = get_setting('real_app_key')
        app_secret = get_setting('real_app_secret')
        url = "https://openapi.koreainvestment.com:9443/oauth2/token"
    else:
        app_key = get_setting('paper_app_key')
        app_secret = get_setting('paper_app_secret')
        url = "https://openapivts.koreainvestment.com:29443/oauth2/token"

    print(f"Testing {mode} mode...")
    print(f"URL: {url}")
    print(f"AppKey: {repr(app_key)[:15]}... (Len: {len(app_key) if app_key else 0})")
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'appkey': app_key,
        'appsecret': app_secret
    }

    try:
        res = requests.post(url, headers=headers, data=data, timeout=5)
        print(f"Response Code: {res.status_code}")
        print(f"Body: {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_kis_connection('REAL')
    print("-" * 30)
    test_kis_connection('PAPER')
