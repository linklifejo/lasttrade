"""
Paper Trading 토큰 발급 직접 테스트
"""
import sys
sys.path.insert(0, '.')

from kiwoom.real_api import RealKiwoomAPI
from database_helpers import get_setting

print("=" * 60)
print("Paper Trading 토큰 발급 테스트")
print("=" * 60)

# 설정 확인
use_mock = get_setting('use_mock_server', True)
is_paper = get_setting('is_paper_trading', False)

print(f"\n[현재 설정]")
print(f"use_mock_server  : {use_mock}")
print(f"is_paper_trading : {is_paper}")

if use_mock:
    print("\n⚠️ 경고: Mock 모드가 활성화되어 있습니다!")
    print("Paper Trading 토큰을 발급받으려면 use_mock_server를 false로 설정하세요.")

# API 객체 생성 및 토큰 발급
print(f"\n[API 객체 생성]")
api = RealKiwoomAPI()
print(f"✅ RealKiwoomAPI 생성 완료")
print(f"   App Key    : {api.app_key[:20]}...")
print(f"   App Secret : {api.app_secret[:20]}...")
print(f"   Host URL   : {api.host_url}")

# 토큰 발급 시도
print(f"\n[토큰 발급 시도]")
print(f"요청 중...")
token = api.get_token()

if token:
    print(f"\n✅ 토큰 발급 성공!")
    print(f"   Token: {token[:50]}...")
    print(f"   Length: {len(token)}")
else:
    print(f"\n❌ 토큰 발급 실패!")
    print(f"\n가능한 원인:")
    print(f"1. API 키 또는 Secret이 잘못되었습니다.")
    print(f"2. 키움 서버에 문제가 있습니다.")
    print(f"3. 네트워크 연결에 문제가 있습니다.")
    print(f"4. 하루 토큰 발급 제한(5회)을 초과했습니다.")
