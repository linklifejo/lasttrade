import requests
import json

def test_token(url, appkey, appsecret, use_json=True):
    headers = {
        'Content-Type': 'application/json; charset=UTF-8' if use_json else 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'client_credentials',
        'appkey': appkey,
        'appsecret': appsecret
    }
    
    try:
        if use_json:
            res = requests.post(url, headers=headers, json=data)
        else:
            res = requests.post(url, headers=headers, data=data)
            
        print(f"Server: {url}")
        print(f"Format: {'JSON' if use_json else 'Form'}")
        print(f"Code: {res.status_code}")
        print(f"Body: {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    from database_helpers import get_setting
    ak = get_setting('real_app_key')
    sk = get_setting('real_app_secret')
    
    real_url = "https://openapi.koreainvestment.com:9443/oauth2/token"
    paper_url = "https://openapivts.koreainvestment.com:29443/oauth2/token"
    
    print("--- Testing Real Key on Real Server ---")
    test_token(real_url, ak, sk, use_json=True)
    test_token(real_url, ak, sk, use_json=False)
    
    print("\n--- Testing Real Key on Paper Server ---")
    test_token(paper_url, ak, sk, use_json=True)
