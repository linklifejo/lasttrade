import requests

try:
    res = requests.get('http://localhost:8080', timeout=5)
    html = res.text
    
    print("=" * 60)
    print("HTML 구조 분석")
    print("=" * 60)
    
    # 1. real_app_key 입력창 존재 여부
    if 'id="real_app_key"' in html:
        print("✅ real_app_key 입력창이 HTML에 존재함")
        
        # value 속성 확인
        if 'value="Loading authentication data..."' in html:
            print("✅ value 속성도 있음 (Loading...)")
        else:
            print("⚠️ value 속성이 다르거나 없음")
    else:
        print("❌ real_app_key 입력창이 HTML에 없음!")
    
    # 2. view-settings 존재 여부
    if 'id="view-settings"' in html:
        print("✅ view-settings 섹션 존재")
        
        # view-settings에 class="view" 있는지
        if 'id="view-settings" class="view"' in html:
            print("✅ view 클래스 있음")
        elif 'id="view-settings" class="view active"' in html:
            print("✅ view active 클래스 있음 (활성화됨)")
        else:
            print("⚠️ view 클래스 상태 확인 필요")
    
    # 3. script_v7.js 로드 여부
    if 'script_v7.js' in html:
        print("✅ script_v7.js 참조 있음")
    else:
        print("❌ script_v7.js 참조 없음!")
    
    # 4. 인증 섹션 헤더 확인
    if '핵심 인증 정보 관리' in html:
        print("✅ 인증 정보 섹션 헤더 존재")
    else:
        print("❌ 인증 정보 섹션 헤더 없음!")
    
    print("\n" + "=" * 60)
    print("결론:")
    print("=" * 60)
    
    if all([
        'id="real_app_key"' in html,
        'id="view-settings"' in html,
        '핵심 인증 정보 관리' in html
    ]):
        print("✅ HTML 구조는 정상입니다.")
        print("⚠️ 문제는 CSS 또는 JavaScript입니다.")
        print("\n다음을 확인해주세요:")
        print("1. 브라우저에서 F12 눌러서 Console 탭 확인")
        print("2. Elements 탭에서 'real_app_key' 검색")
        print("3. 해당 요소의 Computed 스타일에서 display 값 확인")
    else:
        print("❌ HTML 구조에 문제가 있습니다!")
        
except Exception as e:
    print(f"❌ 오류: {e}")
