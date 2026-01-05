import requests

try:
    # script_v7.js 파일이 서빙되는지 확인
    res = requests.get('http://localhost:8080/static/script_v7.js', timeout=5)
    
    if res.status_code == 200:
        print(f"✅ script_v7.js 로드 성공 (크기: {len(res.text)} 바이트)")
        
        # loadSettings 함수가 있는지 확인
        if 'function loadSettings' in res.text or 'async function loadSettings' in res.text:
            print("✅ loadSettings 함수 존재")
        else:
            print("❌ loadSettings 함수 없음!")
            
        # DOMContentLoaded에서 loadSettings 호출하는지 확인
        if 'loadSettings()' in res.text:
            print("✅ loadSettings() 호출 코드 존재")
        else:
            print("❌ loadSettings() 호출 코드 없음!")
            
    else:
        print(f"❌ script_v7.js 로드 실패: {res.status_code}")
        
except Exception as e:
    print(f"❌ 오류: {e}")
