from kiwoom_adapter import fn_kt00004, get_api
from get_setting import get_setting
from logger import logger

# Paper 모드 토큰 가져오기
api = get_api()
token = None

try:
    # 보유 종목 조회
    holdings = fn_kt00004(token=token)
    
    if holdings:
        print("=" * 80)
        print("현재 보유 종목 상태")
        print("=" * 80)
        
        split_cnt = int(float(get_setting('split_buy_cnt', 1)))
        single_strategy = get_setting('single_stock_strategy', 'WATER')
        
        print(f"\n설정:")
        print(f"  - 분할 매수 횟수: {split_cnt}회")
        print(f"  - 전략: {single_strategy}")
        print()
        
        for idx, stock in enumerate(holdings, 1):
            code = stock['stk_cd']
            name = stock['stk_nm']
            pl_rt = float(stock.get('pl_rt', 0))
            qty = int(stock.get('rmnd_qty', 0))
            
            # 매입금액 계산
            pchs_amt = 0
            if 'pchs_amt' in stock and stock['pchs_amt']:
                pchs_amt = int(stock['pchs_amt'])
            elif 'pur_amt' in stock and stock['pur_amt']:
                pchs_amt = int(stock['pur_amt'])
            else:
                try:
                    pchs_amt = float(stock.get('pchs_avg_pric', 0)) * qty
                except:
                    pchs_amt = 0
            
            # watering_step 확인
            step_info = stock.get('watering_step', '정보없음')
            
            print(f"{idx}. {name} ({code})")
            print(f"   수익률: {pl_rt}%")
            print(f"   보유수량: {qty}주")
            print(f"   매입금액: {pchs_amt:,}원")
            print(f"   물타기 단계: {step_info}")
            print(f"   → MAX 도달? {'✅ YES' if pl_rt < -0.01 else '❌ NO (수익 중)'}")
            print()
        
        print("=" * 80)
        print(f"\n💡 판단: split_buy_cnt={split_cnt}일 때, {split_cnt}차 완료 + 손실이면 매도해야 함")
        
    else:
        print("보유 종목이 없습니다.")
        
except Exception as e:
    print(f"오류 발생: {e}")
    import traceback
    traceback.print_exc()
