import requests
import json

def test_paper():
    from database_helpers import get_setting
    ak = get_setting('paper_app_key')
    sk = get_setting('paper_app_secret')
    url = "https://openapivts.koreainvestment.com:29443/oauth2/token"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "grant_type": "client_credentials",
        "appkey": ak,
        "appsecret": sk
    }
    
    res = requests.post(url, headers=headers, json=data)
    print(f"Paper Test (JSON) - Code: {res.status_code}")
    print(f"Body: {res.text}")

    headers_form = {'Content-Type': 'application/x-www-form-urlencoded'}
    res_form = requests.post(url, headers=headers_form, data=data)
    print(f"Paper Test (Form) - Code: {res_form.status_code}")
    print(f"Body: {res_form.text}")

if __name__ == "__main__":
    test_paper()
