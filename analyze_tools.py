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

def calculate_ma(prices, period):
    """이동평균 계산"""
    if len(prices) < period: return None
    return sum(prices[-period:]) / period

def get_technical_indicators(code, timeframe='1m'):
    """종목의 성향(MA 이격도, Trend 등)을 분석하기 위한 지표 뭉치 반환"""
    from database import get_candle_history_sync
    prices = get_candle_history_sync(code, timeframe, limit=60)
    
    if not prices: return None
    
    curr_price = prices[-1]
    ma5 = calculate_ma(prices, 5)
    ma20 = calculate_ma(prices, 20)
    rsi = calculate_rsi(prices, 14)
    
    # 이격도 (Disparity)
    disparity_5 = (curr_price / ma5 * 100) if ma5 else 100
    disparity_20 = (curr_price / ma20 * 100) if ma20 else 100
    
    # 추세 강도 (MA5 > MA20 이면 정배열 가중치)
    trend = "UP" if (ma5 and ma20 and ma5 > ma20) else "DOWN"
    
    return {
        'price': curr_price,
        'ma5': ma5,
        'ma20': ma20,
        'rsi': rsi,
        'disparity_5': disparity_5,
        'disparity_20': disparity_20,
        'trend': trend
    }
