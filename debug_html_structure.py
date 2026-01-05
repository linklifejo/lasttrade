import requests
from bs4 import BeautifulSoup

try:
    res = requests.get('http://localhost:8080', timeout=5)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # view-settings 찾기
    settings_view = soup.find('div', {'id': 'view-settings'})
    
    if settings_view:
        print("✅ view-settings 발견")
        
        # 인증 정보 입력창 찾기
        real_key = soup.find('input', {'id': 'real_app_key'})
        
        if real_key:
            print(f"✅ real_app_key 입력창 발견")
            print(f"   - value 속성: {real_key.get('value', '(없음)')}")
            print(f"   - style: {real_key.get('style', '(없음)')[:100]}...")
            
            # 부모 요소 확인
            parent = real_key.parent
            print(f"   - 부모 태그: {parent.name}")
            print(f"   - 부모 style: {parent.get('style', '(없음)')[:100]}...")
            
            # 조상 요소 중 display:none 찾기
            current = real_key
            hidden_found = False
            for i in range(10):
                current = current.parent
                if not current:
                    break
                style = current.get('style', '')
                class_attr = current.get('class', [])
                
                if 'display: none' in style or 'display:none' in style:
                    print(f"❌ 숨겨진 부모 발견! {current.name} (레벨 {i+1})")
                    print(f"   style: {style}")
                    hidden_found = True
                    break
                
                if 'view' in class_attr and current.get('id') != 'view-settings':
                    print(f"⚠️ 다른 view 안에 있음: {current.get('id')}")
                    hidden_found = True
                    break
            
            if not hidden_found:
                print("✅ 숨김 처리된 부모 없음 - CSS 문제일 수 있음")
        else:
            print("❌ real_app_key 입력창을 찾을 수 없음!")
    else:
        print("❌ view-settings를 찾을 수 없음!")
        
except Exception as e:
    print(f"❌ 오류: {e}")
