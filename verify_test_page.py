import requests

try:
    # 1. 테스트 페이지 확인
    print("=" * 60)
    print("1. 테스트 페이지 HTML 확인")
    print("=" * 60)
    res = requests.get('http://localhost:8080/test', timeout=5)
    if res.status_code == 200:
        print(f"✅ 페이지 로드 성공 (길이: {len(res.text)} 글자)")
        if 'real_app_key' in res.text:
            print("✅ HTML에 'real_app_key' 입력창 존재")
        else:
            print("❌ HTML에 'real_app_key' 입력창 없음!")
    else:
        print(f"❌ 페이지 로드 실패: {res.status_code}")
    
    print("\n" + "=" * 60)
    print("2. API 응답 확인")
    print("=" * 60)
    res2 = requests.get('http://localhost:8080/api/settings', timeout=5)
    if res2.status_code == 200:
        data = res2.json()
        print(f"✅ API 응답 성공 (키 개수: {len(data)})")
        print(f"   - real_app_key: {'있음' if data.get('real_app_key') else '없음'}")
        print(f"   - real_app_secret: {'있음' if data.get('real_app_secret') else '없음'}")
        if data.get('real_app_key'):
            print(f"   - 값 미리보기: {data['real_app_key'][:10]}...")
    else:
        print(f"❌ API 실패: {res2.status_code}")
        
except Exception as e:
    print(f"❌ 오류: {e}")
