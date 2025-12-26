import requests
import json

try:
    resp = requests.get('http://localhost:8080/api/status')
    data = resp.json()
    summary = data.get('summary', {})
    holdings = data.get('holdings', [])
    
    print(f"API Mode: {summary.get('api_mode')}")
    print(f"Total Holdings: {len(holdings)}")
    for h in holdings:
        print(f" - {h.get('stk_nm')} ({h.get('stk_cd')})")
        
except Exception as e:
    print(f"Error: {e}")
