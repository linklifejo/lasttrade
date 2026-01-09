
import sys
import math
from database_helpers import get_setting, save_setting
from kiwoom_adapter import fn_kt00001 as get_balance
from get_token import get_token_sync
from logger import logger

def optimize_settings():
    """
    [자금 기반 설정 최적화]
    현재 예수금과 목표 종목 수를 기반으로, 
    물리적으로 가능한 최대 분할 매수 횟수를 계산하여 설정을 자동 보정합니다.
    """
    try:
        # 1. 토큰 및 예수금 확보
        token = get_token_sync()
        if not token:
            logger.error("[AutoOptimize] 토큰 발급 실패로 최적화 스킵")
            return

        balance_info = get_balance(token=token)
        if not balance_info:
            logger.error("[AutoOptimize] 예수금 조회 실패로 최적화 스킵")
            return
            
        # balance_info: (주문가능금액, 총평가금, 예수금)
        available_cash = int(balance_info[0])
        
        # 2. 설정값 로드
        target_cnt = int(float(get_setting('target_stock_count', 1)))
        if target_cnt < 1: target_cnt = 1
        
        current_split_cnt = int(get_setting('split_buy_cnt', 5))
        min_amt = int(get_setting('min_purchase_amount', 2000)) # 최소 주문 금액 (안전하게 2000원 이상 잡음)
        capital_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0
        
        # 3. 계산 (우선순위: 분할 횟수 보장 > 종목 수)
        # 현재 설정된 분할 횟수(예: 5회)를 완주하기 위해 1종목당 필요한 '최소' 예산 계산
        
        required_budget_per_stock = 0
        for i in range(1, current_split_cnt + 1):
            if i == 1: weight = 1
            elif i == 2: weight = 1
            else: weight = 2**(i - 2)
            required_budget_per_stock += (min_amt * weight)
            
        # 1:1:2:4... 구조상 마지막에 배정되는 금액이 가장 크므로 여유분 고려 (안전율 1.1배)
        required_budget_per_stock = int(required_budget_per_stock * 1.1)
        
        # 4. 시뮬레이션: 내 돈으로 이 예산(5회 풀매수)을 몇 종목이나 감당 가능한가?
        trading_budget = available_cash * capital_ratio
        max_possible_stocks = int(trading_budget // required_budget_per_stock)
        
        if max_possible_stocks < 1: max_possible_stocks = 1 # 최소 1종목은 해야 함
        
        logger.info(f"🔍 [자금 점검] {current_split_cnt}회 완주를 위한 1종목 필수금액: {required_budget_per_stock:,.0f}원 (가용총알: {trading_budget:,.0f}원)")
        
        # 5. 결과 반영
        # "2종목 4회 vs 1종목 5회" -> 1종목 5회를 선택 (종목 수 희생)
        if max_possible_stocks < target_cnt:
            save_setting('target_stock_count', max_possible_stocks)
            logger.warning(f"⚠️ [설정 자동 보정] 예산 부족으로 '{current_split_cnt}회 분할'을 보장하기 위해 목표 종목 수 축소: {target_cnt}개 -> {max_possible_stocks}개")
            print(f"Update: target_stock_count {target_cnt} -> {max_possible_stocks}")
        else:
            logger.info(f"✅ [설정 점검] 현재 예산으로 {target_cnt}개 종목 모두 {current_split_cnt}회 분할 매수 가능")

    except Exception as e:
        logger.error(f"[AutoOptimize] 실행 중 오류: {e}")

if __name__ == "__main__":
    optimize_settings()
