import sys
import os
import time

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kiwoom.mock_api import MockKiwoomAPI
from database_helpers import save_setting, get_setting

def test_mock_danta_logic():
    print("🧪 Mock 서버 단타 로직 테스트 시작...")
    
    # 1. 설정값 강제 세팅 (확인용)
    save_setting('mock_tax_rate', 0.3)
    save_setting('mock_slippage_rate', 0.05)
    save_setting('initial_asset', 500000000)
    save_setting('trading_capital_ratio', 100)
    
    api = MockKiwoomAPI()
    token = api.get_token()
    
    # 삼성전자(005930) 정보 확인
    price_info = api.get_current_price('005930', token)
    base_price = int(price_info['stk_prpr'])
    print(f"📊 현재가: {base_price:,}원")
    
    # 2. 매수 테스트 (슬리피지 확인)
    print("\n🛒 매수 테스트 진행 (10주)...")
    res, msg = api.buy_stock('005930', '10', str(base_price), token)
    print(f"결과: {res}, 메시지: {msg}")
    
    # 체결 로그를 기다림
    time.sleep(1)
    
    # 3. 매도 테스트 (슬리피지 + 세금 확인)
    print("\n💰 매도 테스트 진행 (10주)...")
    res, msg = api.sell_stock('005930', '10', token)
    print(f"결과: {res}, 메시지: {msg}")
    
    # 체결 로그를 기다림
    time.sleep(1)
    
    print("\n✅ 테스트 완료. 로그를 통해 슬리피지와 세금이 적용된 금액을 확인하세요.")

if __name__ == "__main__":
    test_mock_danta_logic()
