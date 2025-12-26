import asyncio
from kiwoom_adapter import get_api, fn_au10001
import json

async def check_outstanding_via_adapter():
    # 1. API 인스턴스 및 토큰 가져오기
    api = get_api()
    token = fn_au10001()
    
    print(f"--- 어댑터 통과 미체결 조회 ---")
    print(f"API Instance: {api.__class__.__name__}")
    
    if not token:
        print("토큰 없음")
        return

    try:
        orders = api.get_outstanding_orders(token)
        print(f"Orders Result Type: {type(orders)}")
        if orders is None:
            print("결과: None (에러 발생 혹은 권한 없음)")
        elif isinstance(orders, list):
            print(f"결과 개수: {len(orders)}")
            for i, o in enumerate(orders):
                print(f"Order {i+1}: {o.get('name')} ({o.get('stk_cd')}), Qty: {o.get('qty')}, Type: {o.get('type')}")
        else:
            print(f"결과: 알 수 없는 형식 {orders}")
    except Exception as e:
        print(f"Error during call: {e}")

if __name__ == "__main__":
    asyncio.run(check_outstanding_via_adapter())
