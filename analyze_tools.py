import pandas as pd
import logging

logger = logging.getLogger("trading_bot")

def calculate_rsi(prices, period=14):
    """
    주어진 가격 리스트로 RSI를 계산합니다.
    """
    if len(prices) < period + 1:
        return None

    try:
        series = pd.Series(prices)
        delta = series.diff()

        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]
    except Exception as e:
        logger.error(f"RSI 계산 오류: {e}")
        return None

def get_rsi_for_timeframe(code, timeframe='1m', period=14):
    """
    특정 타임프레임(1m, 3m)의 RSI를 DB 데이터를 사용하여 계산합니다.
    """
    from database import get_candle_history_sync
    # RSI 14를 위해 최소 30개 정도의 데이터를 가져옵니다.
    prices = get_candle_history_sync(code, timeframe, limit=period * 2 + 5)
    return calculate_rsi(prices, period)
