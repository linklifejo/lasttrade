
import sys
import os
from kiwoom_adapter import get_outstanding_orders, get_token

def test_outstanding():
    print("🚀 [TEST] 미체결 내역 조회 함수 검증 시작")
    
    try:
        # 토큰 발급 (Mock이면 가짜 토큰)
        token = get_token()
        print(f"✅ 토큰 획득: {str(token)[:10]}...")
        
        # 함수 호출
        orders = get_outstanding_orders(token)
        
        print(f"✅ 함수 호출 성공! 반환 타입: {type(orders)}")
        print(f"📊 미체결 내역: {orders}")
        
        if isinstance(orders, list):
            print("🎉 [PASS] 검증 통과: 리스트 타입 반환 확인")
        else:
            print("❌ [FAIL] 검증 실패: 리스트가 아님")
            
    except Exception as e:
        print(f"❌ [ERROR] 테스트 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_outstanding()
