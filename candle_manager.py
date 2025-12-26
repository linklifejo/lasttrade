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
        """1분마다 호출되어 1분봉 및 3분봉 생성"""
        now = datetime.datetime.now()
        current_minute = now.minute
        
        if self.last_minute is None:
            self.last_minute = current_minute
            return

        if current_minute != self.last_minute:
            # 1분 지남 -> 캔들 생성
            logger.info(f"🕯️ [CandleManager] {self.last_minute}분 캔들 생성 시작...")
            
            for code, prices in self.ticks.items():
                if not prices: continue
                
                # 1분봉 생성
                o, h, l, c = prices[0], max(prices), min(prices), prices[-1]
                await log_candle(code, '1m', o, h, l, c)
                
                # 3분봉 처리 (0, 3, 6... 분에 저장)
                if current_minute % 3 == 0:
                    # 3분봉은 1분봉 데이터를 3개 모아서 하는게 정확하지만, 
                    # 여기서는 단순하게 현재 슬롯에 3분봉 데이터로 기록 (학습용 기반)
                    # 실제 정밀한 3분봉은 DB 쿼리 시 1분봉 3개를 묶어서 처리하는게 더 좋음
                    await log_candle(code, '3m', o, h, l, c)
            
            # 틱 초기화
            self.ticks = {}
            self.last_minute = current_minute

candle_manager = CandleManager()
