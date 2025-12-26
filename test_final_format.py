import requests
import json

def test_final():
    from database_helpers import get_setting
    ak = get_setting('real_app_key')
    sk = get_setting('real_app_secret')
    url = "https://openapi.koreainvestment.com:9443/oauth2/token"
    
    data = {
        "grant_type": "client_credentials",
        "appkey": ak,
        "appsecret": sk
    }
    
    # Try with raw string and no charset in header
    headers = {'Content-Type': 'application/json'}
    res = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"Final Test - Code: {res.status_code}")
    print(f"Body: {res.text}")

if __name__ == "__main__":
    test_final()
