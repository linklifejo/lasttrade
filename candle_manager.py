import time
import datetime
from logger import logger
from database import log_candle

class CandleManager:
    def __init__(self):
        self.ticks = {} # {code: [prices]}
        self.last_minute = None
        
    def add_tick(self, code, price):
        """실시간 틱(현재가) 추가"""
        if code not in self.ticks:
            self.ticks[code] = []
        self.ticks[code].append(price)
        
    async def process_minute_candles(self):
        """1분마다 호출되어 1m, 3m, 5m, 60m 캔들 생성"""
        now = datetime.datetime.now()
        current_minute = now.minute
        current_hour = now.hour
        
        if self.last_minute is None:
            self.last_minute = current_minute
            return

        if current_minute != self.last_minute:
            # 1분 지남 -> 캔들 생성
            logger.info(f"🕯️ [CandleManager] {self.last_minute}분 캔들 생성 및 기록...")
            
            for code, prices in self.ticks.items():
                if not prices: continue
                
                o, h, l, c = prices[0], max(prices), min(prices), prices[-1]
                v = len(prices) # 단순 틱 수로 거래량 대체 (실전에서는 API 거래량 사용)
                
                # 1분봉 저장
                await log_candle(code, '1m', o, h, l, c, v)
                
                # 5분봉 저장 (5, 10, 15... 분)
                if (current_minute + 1) % 5 == 0:
                    await log_candle(code, '5m', o, h, l, c, v)
                
                # 60분봉 저장 (정각 직전)
                if (current_minute + 1) % 60 == 0:
                    await log_candle(code, '60m', o, h, l, c, v)
            
            # 틱 초기화
            self.ticks = {}
            self.last_minute = current_minute

    def get_context_60m(self, code):
        """60분봉 기준의 현재 컨텍스트(추세, 위치) 반환"""
        from database import get_candle_history_sync
        # 최근 60분봉 2개 조회 (비교용)
        closes = get_candle_history_sync(code, '60m', 20)
        
        if not closes or len(closes) < 1:
            return {"trend": 0, "pos": 0.5, "ma_gap": 0}
            
        curr_c = closes[-1]
        # 추세: 단순 이평선(MA20) 기준
        ma20 = sum(closes) / len(closes)
        trend = 1 if curr_c > ma20 else -1
        
        # 이격도
        ma_gap = ((curr_c - ma20) / ma20 * 100) if ma20 > 0 else 0
        
        return {
            "trend_60m": trend,
            "ma_gap_60m": round(ma_gap, 2),
            "ma20_60m": round(ma20, 0)
        }

candle_manager = CandleManager()
