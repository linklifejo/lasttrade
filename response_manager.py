import asyncio
import time
import datetime
from logger import logger
from database import get_db_connection

class ResponseManager:
    """시그널 발생 후 가격 변화(대응 데이터)를 수학적으로 추적하는 매니저"""
    def __init__(self):
        self.pending_signals = [] # [(signal_id, code, entry_price, timestamp)]
        
    def add_signal(self, signal_id, code, price):
        self.pending_signals.append({
            'id': signal_id,
            'code': code,
            'entry_price': price,
            'start_time': time.time(),
            'checkpoints': {
                '1m': False,
                '5m': False
            },
            'max_profit': 0,
            'max_drawdown': 0
        })

    async def update_metrics(self, current_prices):
        """메인 루프에서 호출되어 실시간으로 수익 현황 및 체크포인트 기록"""
        now = time.time()
        to_save = []
        
        for sig in self.pending_signals:
            code = sig['code']
            if code not in current_prices: continue
            
            curr_price = current_prices[code]
            change = (curr_price - sig['entry_price']) / sig['entry_price'] * 100
            
            # 최대 수익/낙폭 갱신
            sig['max_profit'] = max(sig['max_profit'], change)
            sig['max_drawdown'] = min(sig['max_drawdown'], change)
            
            # 1분 체크포인트
            if not sig['checkpoints']['1m'] and (now - sig['start_time'] >= 60):
                sig['capture_1m'] = change
                sig['checkpoints']['1m'] = True
                
            # 5분 체크포인트 및 종료
            if not sig['checkpoints']['5m'] and (now - sig['start_time'] >= 300):
                sig['capture_5m'] = change
                sig['checkpoints']['5m'] = True
                to_save.append(sig)
                
        # 완료된 데이터 DB 저장
        for sig in to_save:
            await self._save_response(sig)
            self.pending_signals.remove(sig)
            
    async def _save_response(self, sig):
        try:
            from database import DB_FILE
            import aiosqlite
            async with aiosqlite.connect(DB_FILE) as db:
                await db.execute('''
                    INSERT INTO response_metrics (signal_id, code, interval_1m_change, interval_5m_change, max_drawdown, max_profit)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (sig['id'], sig['code'], sig.get('capture_1m', 0), sig.get('capture_5m', 0), sig['max_drawdown'], sig['max_profit']))
                await db.commit()
            logger.info(f"📊 [Math Response] ID:{sig['id']} 대응 데이터 저장 완료 (1m:{sig.get('capture_1m', 0):.2f}%, 5m:{sig.get('capture_5m', 0):.2f}%)")
        except Exception as e:
            logger.error(f"대응 데이터 저장 실패: {e}")

response_manager = ResponseManager()
