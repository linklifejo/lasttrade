import pandas as pd
import logging

logger = logging.getLogger("trading_bot")

def calculate_rsi(prices, period=14):
    """
    주어진 가격 리스트로 RSI를 계산합니다.
    Args:
        prices (list): 가격 리스트 (시간순, 최근이 마지막)
        period (int): RSI 기간 (기본 14)
    Returns:
        float: 최근 RSI 값 (데이터 부족 시 None)
    """
    if len(prices) < period + 1:
        return None

    try:
        series = pd.Series(prices)
        delta = series.diff()

        # 상승폭, 하락폭 계산 (절대값)
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]
    except Exception as e:
        logger.error(f"RSI 계산 오류: {e}")
        return None
