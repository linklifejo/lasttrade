import requests
import json

try:
    url = "http://localhost:5000/api/command"
    headers = {'Content-Type': 'application/json'}
    data = {'command': 'start'}
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        print(f"✅ 명령 전송 성공: {response.json()}")
    else:
        print(f"❌ 명령 전송 실패: {response.status_code} - {response.text}")
except Exception as e:
    print(f"❌ 연결 실패: {e}")
    print("웹 서버가 죽어있을 수 있습니다.")
