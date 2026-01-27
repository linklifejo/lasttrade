"""
키움 API 통합 어댑터

기존 코드와의 호환성을 유지하면서 Mock/Real API를 사용할 수 있도록 합니다.
"""

from typing import List, Dict, Tuple, Optional
import json
import os
from kiwoom.factory import create_kiwoom_api
from logger import logger
import config

from config import socket_url
from logger import logger

# ========== 전역 상태 및 API 인스턴스 관리 ==========

# 전역 설정 추적
_api_instance = None
_last_mock_setting = None
_last_paper_setting = None
_last_account = None
_last_real_key = None
_last_real_secret = None
_last_paper_key = None
_last_paper_secret = None

def get_api():
    """API 인스턴스 가져오기 (설정 변경 감지 및 자동 스위칭)"""
    return get_active_api()

def get_active_api():
    """API 인스턴스 가져오기 (실제 동작 로직)"""
    global _api_instance, _last_mock_setting, _last_paper_setting, _last_account, \
           _last_real_key, _last_real_secret, _last_paper_key, _last_paper_secret
    
    # 1. DB에서 실시간 상태 확인
    try:
        from database_helpers import get_setting
        current_mock_setting = get_setting('use_mock_server', False)
        current_paper_setting = get_setting('is_paper_trading', True)
        current_account = get_setting('my_account', None)
        
        # [NEW] 키 변경 감지 추가
        current_real_key = get_setting('real_app_key', None)
        current_real_secret = get_setting('real_app_secret', None)
        current_paper_key = get_setting('paper_app_key', None)
        current_paper_secret = get_setting('paper_app_secret', None)
    except:
        current_mock_setting = True
        current_paper_setting = True
        current_account = None
        current_real_key = current_real_secret = current_paper_key = current_paper_secret = None
        
    # 2. 설정이 하나라도 바뀌었으면 기존 인스턴스 파기 및 config 리로드
    # [Fix] 타입 차이(bool vs str)로 인한 무한 리부트 방지를 위해 str() 변환 후 비교
    has_changed = False
    if _last_mock_setting is not None and str(_last_mock_setting).upper() != str(current_mock_setting).upper(): has_changed = True
    if _last_paper_setting is not None and str(_last_paper_setting).upper() != str(current_paper_setting).upper(): has_changed = True
    if _last_account is not None and str(_last_account) != str(current_account): has_changed = True
    
    # 키 변경 감지
    if _last_real_key is not None and str(_last_real_key) != str(current_real_key): has_changed = True
    if _last_real_secret is not None and str(_last_real_secret) != str(current_real_secret): has_changed = True
    
    if has_changed:
        mode_str = "MOCK" if current_mock_setting else "REAL"
        acc_str = "모의" if current_paper_setting else "실전"
        logger.warning(f"🔄 환경/키 변경 감지: [{acc_str} 계좌 + {mode_str} API] 설정을 리로드합니다.")
        
        # 키값 및 URL도 바뀌어야 하므로 config 모듈 강제 리로드
        import importlib
        importlib.reload(config)
        
        reset_api()
    
    # 3. 인스턴스 생성 또는 반환
    if _api_instance is None:
        _last_mock_setting = current_mock_setting
        _last_paper_setting = current_paper_setting
        _last_account = current_account
        _last_real_key = current_real_key
        _last_real_secret = current_real_secret
        _last_paper_key = current_paper_key
        _last_paper_secret = current_paper_secret
        _api_instance = create_kiwoom_api(current_mock_setting)
        
    return _api_instance


def reset_api():
    """API 인스턴스 재설정 (설정 변경 시 사용)"""
    global _api_instance
    _api_instance = None
    logger.info("API 인스턴스가 재설정되었습니다")


# ========== 기존 함수명 호환성 유지 ==========

def fn_au10001() -> Optional[str]:
    """접근토큰 발급 (login.py 호환)"""
    return get_api().get_token()


def fn_kt00001(cont_yn='N', next_key='', token=None, max_retries=3) -> Tuple[int, int, int]:
    """예수금상세현황요청 (check_bal.py 호환)"""
    if token is None:
        token = fn_au10001()
    return get_api().get_balance(token)


def get_account_data(cont_yn='N', next_key='', token=None, max_retries=2) -> Tuple[List[Dict], Dict]:
    """계좌평가현황요청 (acc_val.py 호환)"""
    if token is None:
        token = fn_au10001()
    return get_api().get_account_data(token)


def fn_kt00004(print_df=False, cont_yn='N', next_key='', token=None) -> List[Dict]:
    """보유 종목 조회 (acc_val.py 호환)"""
    if token is None:
        token = fn_au10001()
    return get_api().get_my_stocks(token, print_df)


def get_total_eval_amt(token=None) -> int:
    """보유 주식의 총 평가금액 (acc_val.py 호환)"""
    if token is None:
        token = fn_au10001()
    return get_api().get_total_eval_amt(token)


def fn_kt10000(stk_cd, ord_qty, ord_uv, cont_yn='N', next_key='', token=None, source='Search') -> Tuple[str, str]:
    """주식 매수주문 (buy_stock.py 호환)"""
    if token is None:
        token = fn_au10001()
    
    api = get_api()
    # [Single Logic] Mock/Real 모두 source 정보를 전달하도록 통일
    # buy_stock 메서드가 source를 지원하는지 확인 (안전장치)
    import inspect
    sig = inspect.signature(api.buy_stock)
    if 'source' in sig.parameters:
        return api.buy_stock(stk_cd, ord_qty, ord_uv, token, source=source)
            
    return api.buy_stock(stk_cd, ord_qty, ord_uv, token)


def fn_ka10004(stk_cd, cont_yn='N', next_key='', token=None) -> float:
    """주식 호가 조회 (check_bid.py 호환)"""
    if token is None:
        token = fn_au10001()
    
    price_data = get_api().get_current_price(stk_cd, token)
    if price_data:
        if isinstance(price_data, dict):
            # API 응답 필드 (sel_fpr_bid 또는 stk_prpr)
            price = price_data.get('sel_fpr_bid') or price_data.get('stk_prpr', 0)
            return float(price)
        else:
            return float(price_data)
    return 0.0


def fn_kt10001(stk_cd, ord_qty, cont_yn='N', next_key='', token=None) -> Tuple[str, str]:
    """주식 매도주문 (sell_stock.py 호환)"""
    if token is None:
        token = fn_au10001()
    return get_api().sell_stock(stk_cd, ord_qty, token)


def get_current_price(stk_cd: str, token=None) -> Optional[int]:
    """실시간 현재가 조회"""
    if token is None:
        token = fn_au10001()
    return get_api().get_current_price(stk_cd, token)




def get_current_api_mode() -> str:
    """현재 API 모드 반환 ('Mock', 'Paper', 또는 'Real')"""
    api = get_api()
    # 클래스 이름으로 확인
    class_name = api.__class__.__name__
    if "Mock" in class_name:
        return "Mock"
    else:
        # Kiwoom API인 경우 PaperTrading 여부 확인
        from database_helpers import get_setting
        if get_setting('is_paper_trading', True):
            return "Paper"
        return "Real"


def fn_opw00007(token=None) -> List[Dict]:
    """일별 체결 내역 조회 (OPW00007)"""
    if token is None:
        token = fn_au10001()
    
    api = get_api()
    # API 인스턴스에 get_trade_history 메서드가 있으면 사용
    if hasattr(api, 'get_trade_history'):
        return api.get_trade_history(token)
    else:
        logger.warning("현재 API는 체결내역 조회를 지원하지 않습니다")
        return []


def fn_kt00007(token=None) -> List[Dict]:
    """미체결 내역 조회 (get_outstanding_orders)"""
    if token is None:
        token = fn_au10001()
    
    api = get_api()
    if hasattr(api, 'get_outstanding_orders'):
        return api.get_outstanding_orders(token)
    else:
        # 미지원 시 빈 리스트 반환 (안전을 위해)
        return []


# ========== Mock 전용 테스트 함수 ==========

def mock_reset_account(initial_cash: int = 10000000):
    """Mock 계좌 초기화 (Mock API에서만 동작)"""
    api = get_api()
    if hasattr(api, 'reset_account'):
        api.reset_account(initial_cash)
        logger.info(f"🎮 Mock 계좌 초기화: {initial_cash:,}원")
    else:
        logger.warning("Real API에서는 계좌 초기화를 할 수 없습니다")


def mock_add_stock(code: str, name: str, base_price: int):
    """Mock 종목 추가 (Mock API에서만 동작)"""
    api = get_api()
    if hasattr(api, 'add_stock'):
        api.add_stock(code, name, base_price)
        logger.info(f"🎮 Mock 종목 추가: {name}({code}) @ {base_price:,}원")
    else:
        logger.warning("Real API에서는 종목을 추가할 수 없습니다")


def mock_set_price(code: str, price: int):
    """Mock 가격 설정 (Mock API에서만 동작)"""
    api = get_api()
    if hasattr(api, 'set_price'):
        api.set_price(code, price)
        logger.info(f"🎮 Mock 가격 설정: {code} = {price:,}원")
    else:
        logger.warning("Real API에서는 가격을 임의로 설정할 수 없습니다")


def mock_simulate_scenario(code: str, scenario: str):
    """
    Mock 시나리오 시뮬레이션 (Mock API에서만 동작)
    
    시나리오:
    - 'surge': 급등 (+5%)
    - 'crash': 급락 (-5%)
    - 'volatile': 변동성 (-3% ~ +3%)
    - 'stable': 안정 (-0.5% ~ +0.5%)
    """
    api = get_api()
    if hasattr(api, 'simulate_price_scenario'):
        api.simulate_price_scenario(code, scenario)
    else:
        logger.warning("Real API에서는 시나리오 시뮬레이션을 할 수 없습니다")


# Aliases for better code readability
# [Move] Defined at end of file to ensure all functions (e.g. fn_opw00007) are defined before assignment
get_my_stocks = fn_kt00004
get_balance = fn_kt00001
get_token = fn_au10001
buy_stock = fn_kt10000
sell_stock = fn_kt10001
get_bid_price = fn_ka10004
get_trade_history = fn_opw00007
get_outstanding_orders = fn_kt00007
