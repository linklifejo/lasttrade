from kiwoom.real_api import RealKiwoomAPI
from logger import logger
import json

def test_connection():
    try:
        api = RealKiwoomAPI()
        
        # 1. 토큰 발급
        print("1. 토큰 발급 시도...")
        token = api.get_token()
        if not token:
            print("❌ 토큰 발급 실패! API Key/Secret을 확인하세요.")
            return

        print(f"✅ 토큰 발급 성공: {token[:20]}...")

        # 2. 잔고 조회
        print("\n2. 잔고 조회 시도...")
        buy_avail, total_eval, deposit = api.get_balance(token)
        print(f"   예수금: {deposit:,.0f}원")
        print(f"   주문가능: {buy_avail:,.0f}원")
        print(f"   총평가: {total_eval:,.0f}원")

        if deposit == 0 and total_eval == 0:
             print("⚠️ 잔고가 0원입니다. 계좌번호나 모의투자 신청 여부를 확인하세요.")

        # 3. 보유 종목 조회
        print("\n3. 보유 종목 조회 시도...")
        stocks = api.get_my_stocks(token)
        print(f"   보유 종목 수: {len(stocks)}개")
        for s in stocks:
            print(f"   - {s['stk_nm']}({s['stk_cd']}): {s['rmnd_qty']}주 (수익률: {s.get('pl_rt')}%)")
            
        print("\n✅ API 연결 테스트 완료")

    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    test_connection()
