import requests, json

try:
    resp = requests.get('http://localhost:8080/api/status')
    data = resp.json()
    print("API Mode:", data['summary']['api_mode'])
    print("Holdings Count:", len(data['holdings']))
    if data['holdings']:
        print("First Holding:", data['holdings'][0]['stk_nm'])
except Exception as e:
    print(f"Error: {e}")
