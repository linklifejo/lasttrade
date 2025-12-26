import asyncio
from kiwoom_adapter import get_api, fn_au10001
from database_helpers import get_setting

async def check_stock_limit():
    api = get_api()
    token = fn_au10001()
    
    print(f"--- 종목 제한 준수 확인 ---\n")
    
    if not token:
        print("토큰 없음")
        return

    # 1. 설정값 확인
    target_count = int(get_setting('target_stock_count', 5))
    print(f"📋 설정된 목표 종목 수: {target_count}개\n")

    # 2. 현재 보유 종목 조회
    holdings = api.get_my_stocks(token)
    
    if not holdings:
        print("✅ 현재 보유 종목 없음 (0개)")
        return
    
    actual_count = len(holdings)
    print(f"📊 실제 보유 종목 수: {actual_count}개\n")
    
    # 3. 보유 종목 목록
    print("보유 종목 상세:")
    print(f"{'종목명':<15} | {'코드':<8} | {'수량':<8} | {'평단가':<10} | {'수익률':<8}")
    print("-" * 70)
    
    for stock in holdings:
        name = stock.get('stk_nm', 'N/A')
        code = stock.get('stk_cd', 'N/A')
        qty = stock.get('rmnd_qty', '0')
        avg_price = stock.get('pchs_avg_pric', '0')
        pl_rt = stock.get('pl_rt', '0')
        
        print(f"{name:<15} | {code:<8} | {qty:<8} | {int(float(str(avg_price).replace(',',''))):>10,} | {pl_rt:>7}%")
    
    # 4. 제한 준수 여부 판정
    print(f"\n{'='*70}")
    if actual_count <= target_count:
        print(f"✅ 종목 제한 준수 중: {actual_count}/{target_count}개 (여유: {target_count - actual_count}개)")
    else:
        print(f"⚠️ 종목 제한 초과: {actual_count}/{target_count}개 (초과: {actual_count - target_count}개)")
    print(f"{'='*70}")

if __name__ == "__main__":
    asyncio.run(check_stock_limit())
