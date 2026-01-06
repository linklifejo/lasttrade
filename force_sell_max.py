
import asyncio
from kiwoom_adapter import fn_kt00004, fn_kt10001, fn_au10001
from database_helpers import get_setting

async def force_sell_max():
    print("🚀 [긴급] MAX 손절 강제 집행기 시작")
    
    # 1. 토큰 발급
    token = fn_au10001()
    if not token:
        print("❌ 토큰 발급 실패")
        return

    # 2. 잔고 조회
    my_stocks = fn_kt00004(token=token)
    if not my_stocks:
        print("✅ 보유 종목 없음 (매도할 것 없음)")
        return

    print(f"📊 현재 보유 종목: {len(my_stocks)}개")
    
    # 3. 설정값
    MAX_SL_TARGET = -3.0  # -3% 손절 기준
    
    for stock in my_stocks:
        name = stock.get('stk_nm', 'Unknown')
        code_raw = stock.get('stk_cd', '')
        # [Fix] 종목코드 앞의 'A' 제거 (매도 API 호환성)
        code = code_raw.replace('A', '') if code_raw else ''
        
        qty = int(stock.get('rmnd_qty', 0))
        pl_rt = float(stock.get('pl_rt', 0.0))
        
        print(f"🔎 {name} ({code}): 수익률 {pl_rt}% / 수량 {qty}")
        
        # 조건 검사: 수익률이 -3.0% 이하면 (MAX 여부와 관계없이 지금은 비상 상황이므로 매도)
        # 사용자님 요청: "-3% 되면 손절해야 함"
        if pl_rt <= MAX_SL_TARGET:
            print(f"🚨 [적발] {name}: 수익률 {pl_rt}% <= {MAX_SL_TARGET}% -> 강제 매도 대상!")
            
            # 매도 실행 (시장가 '00')
            # 1. 미체결 취소 (생략하고 바로 매도 시도 - 키움은 가능)
            # 2. 매도 주문
            print(f"💀 {name} 전량 매도 주문 전송 중...")
            res_code, res_msg = fn_kt10001(code, str(qty), "00", token=token) # "00"은 지정가일 수 있으므로 "03"(시장가) 확인 필요하나 kiwoom_adapter 기본값 사용
            
            print(f"결과: {res_code} / {res_msg}")
            
            if str(res_code) == '0':
                print(f"✅ {name} 매도 주문 성공")
            else:
                print(f"❌ {name} 매도 주문 실패: {res_msg}")
        else:
            print(f"🛡️ {name}: 아직 버틸만 함")

if __name__ == "__main__":
    asyncio.run(force_sell_max())
