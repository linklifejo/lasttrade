import asyncio
from kiwoom_adapter import get_api, fn_au10001
import json

async def show_outstanding():
    # 1. API 인스턴스 및 토큰 가져오기
    api = get_api()
    token = fn_au10001()
    
    print(f"--- 미체결 주문 조회 ---")
    print(f"API Mode: {api.__class__.__name__}")
    
    if not token:
        print("토큰을 가져오지 못했습니다.")
        return

    # 2. 미체결 주문 조회
    # RealKiwoomAPI나 MockKiwoomAPI 모두 get_outstanding_orders 메서드를 가지고 있음
    if hasattr(api, 'get_outstanding_orders'):
        orders = api.get_outstanding_orders(token)
        
        if not orders:
            print("현재 미체결 주문이 없습니다.")
        else:
            print(f"총 {len(orders)}건의 미체결 주문이 있습니다.\n")
            # 헤더 출력
            print(f"{'종목명':<12} | {'코드':<8} | {'유형':<6} | {'가격':<10} | {'수량':<6} | {'미체결':<6} | {'주문번호':<10}")
            print("-" * 80)
            
            for o in orders:
                name = o.get('stk_nm', 'N/A')
                code = o.get('stk_cd', o.get('code', 'N/A'))
                tp = o.get('type', o.get('ord_tp', 'N/A'))
                # 유형 한글화
                tp_str = "매수" if tp in ['buy', '01'] else "매도" if tp in ['sell', '02'] else tp
                
                ord_no = o.get('ord_no', 'N/A')
                qty = o.get('qty', 0)
                unfilled = o.get('qty', 0) # ka10075 normalized qty is already oso_qty
                
                # [Fix] Price formatting
                try:
                    price = o.get('price', 0)
                    p_str = f"{int(price):10,}"
                except:
                    p_str = f"{str(o.get('price', '0')):>10}"
                
                print(f"{name:<12} | {code:<8} | {tp_str:<6} | {p_str} | {qty:<6} | {unfilled:<6} | {ord_no:<10}")
    else:
        print("현재 API에서 미체결 조회를 지원하지 않습니다.")

if __name__ == "__main__":
    asyncio.run(show_outstanding())
