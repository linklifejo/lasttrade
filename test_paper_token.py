import sqlite3
import requests
import json

# DB에서 Paper API 키 가져오기
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute("SELECT value FROM settings WHERE key = 'paper_app_key'")
paper_key = cursor.fetchone()[0]
cursor.execute("SELECT value FROM settings WHERE key = 'paper_app_secret'")
paper_secret = cursor.fetchone()[0]
conn.close()

print("=" * 60)
print("모의투자 API 키 확인 및 토큰 발급 테스트")
print("=" * 60)
print(f"Paper AppKey: {paper_key[:20]}... (길이: {len(paper_key)})")
print(f"Paper AppSecret: {paper_secret[:20]}... (길이: {len(paper_secret)})")
print()

# 모의투자 URL
url = "https://openapivts.koreainvestment.com:29443/oauth2/token"

headers = {
    "content-type": "application/x-www-form-urlencoded"
}

data = {
    "grant_type": "client_credentials",
    "appkey": paper_key,
    "appsecret": paper_secret
}

print(f"요청 URL: {url}")
print(f"Content-Type: {headers['content-type']}")
print()
print("토큰 발급 시도 중...")
print()

try:
    response = requests.post(url, headers=headers, data=data, timeout=10)
    
    print(f"응답 코드: {response.status_code}")
    print(f"응답 내용:")
    
    try:
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if response.status_code == 200:
            token = result.get('access_token')
            print(f"\n✅ 모의투자 토큰 발급 성공!")
            print(f"Token: {token[:30]}...")
            print(f"\n🎉 모의투자 API 키가 정상 작동합니다!")
            print(f"\n📌 Paper Trading 모드로 봇을 시작할 수 있습니다!")
        else:
            print(f"\n❌ 모의투자 토큰 발급 실패")
            print(f"에러 코드: {result.get('error_code')}")
            print(f"에러 메시지: {result.get('error_description')}")
    except:
        print(response.text)
        
except Exception as e:
    print(f"❌ 오류 발생: {e}")
