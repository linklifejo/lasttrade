import sqlite3
import time
import random
import os
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from .base_api import KiwoomAPI
from logger import logger
from database_helpers import DB_FILE, get_db_connection, get_setting

class MockKiwoomAPI(KiwoomAPI):
    """키움 가상 서버 구현 (SQLite DB 기반)"""
    
    def __init__(self, data_dir: str = None):
        logger.info("🎮 MockKiwoomAPI.__init__ 시작")
        # 가상 토큰
        self.token = "MOCK_TOKEN_12345"
        
        # 초기 데이터 로드 또는 생성
        self._initialize_db_data()
        
        # 마지막 가격 업데이트 시간
        self.last_price_update_time = 0
        self.price_update_interval = 0.2  # 0.2초마다 업데이트 (더 생동감 있는 시뮬레이션)
        
        # [미체결 주문 추적] Mock 모드에서도 미체결 주문 관리
        self.outstanding_orders = []  # 미체결 주문 리스트
        self.order_counter = 1000  # 주문번호 카운터
        
        # [Scenario Engine] 시나리오 상태 추적
        self.current_scenario = None
        self.scenario_start_time = 0
        self.scenario_data = {}
        
        logger.info(f"🎮 Mock API (DB Mode) 초기화 완료")
    
    def _initialize_db_data(self):
        """초기 가상 데이터 생성 (DB)"""
        logger.info("🎮 MockKiwoomAPI._initialize_db_data 시작")
        try:
            # 설정 조회 (DB 연결 밖에서 수행하여 교착 상태 방지)
            initial_cash = self._get_initial_cash_from_settings()
            logger.info(f"🎮 초기 자금 설정 로드 완료: {initial_cash:,}원")
            
            with get_db_connection() as conn:
                # 1. 초기 자금 설정
                conn.execute('''
                    INSERT OR IGNORE INTO mock_account (id, cash, total_eval, updated_at)
                    VALUES (1, ?, ?, datetime("now"))
                ''', (initial_cash, initial_cash))
                
                # 2. 주식 리스트 설정 (rt_search.py의 mock_stocks와 일치시킴)
                initial_stocks = [
                    # 대형 고가주
                    ("005930", "삼성전자", 70000), ("000660", "SK하이닉스", 130000), ("035420", "NAVER", 210000), 
                    ("051910", "LG화학", 480000), ("068270", "셀트리온", 180000), ("006400", "삼성SDI", 450000), ("005490", "POSCO홀딩스", 470000),
                    # 중형 중가주
                    ("035720", "카카오", 55000), ("105560", "KB금융", 52000), ("055550", "신한지주", 38000), 
                    ("000270", "기아", 95000), ("005380", "현대차", 190000), ("012330", "현대모비스", 220000), ("028260", "삼성물산", 120000),
                    ("096770", "SK이노베이션", 135000), ("009540", "HD현대중공업", 120000), ("003550", "LG", 80000), 
                    ("066570", "LG전자", 100000), ("018260", "삼성에스디에스", 140000), ("352820", "하이브", 230000),
                    # 저가주 및 동전주
                    ("003280", "흥아해운", 2300), ("001250", "GS글로벌", 2500), ("001520", "동양", 1200), 
                    ("000890", "보해양조", 600), ("000040", "KR모터스", 500), ("003850", "보령", 9000),
                    ("001430", "세아베스틸", 22000), ("010100", "한국무브넥스", 5200),
                    ("000320", "노루페인트", 8500), ("005110", "한창", 800)
                ]
                conn.executemany('INSERT OR IGNORE INTO mock_stocks (code, name, base_price) VALUES (?, ?, ?)', initial_stocks)
                
                # 3. 초기 가격 설정
                for code, name, base_price in initial_stocks:
                    conn.execute('''
                        INSERT OR IGNORE INTO mock_prices (code, current, open, high, low, last_update)
                        VALUES (?, ?, ?, ?, ?, datetime("now"))
                    ''', (code, base_price, base_price, int(base_price*1.02), int(base_price*0.98)))
                
                conn.commit()
        except Exception as e:
            logger.error(f"🎮 Mock DB 초기화 실패: {e}")

    def _get_initial_cash_from_settings(self) -> int:
        try:
            initial_asset = int(get_setting('initial_asset', 500000000))
            capital_ratio = float(get_setting('trading_capital_ratio', 100)) / 100.0
            return int(initial_asset * capital_ratio)
        except:
            return 500000000

    def _update_prices(self, force: bool = False):
        now = time.time()
        if not force and (now - self.last_price_update_time < self.price_update_interval):
            return
        self.last_price_update_time = now
        
        try:
            # 1. 활성 시나리오 확인
            with get_db_connection() as conn:
                row = conn.execute('SELECT id, name, type, params_json FROM sim_scenarios WHERE is_active = 1 LIMIT 1').fetchone()
                if row:
                    scenario_type = row['type']
                    import json
                    params = json.loads(row['params_json'])
                    
                    if self.current_scenario != row['id']:
                        self.current_scenario = row['id']
                        self.scenario_start_time = now
                        logger.info(f"🎮 [Scenario Change] 신규 시나리오 활성화: {row['name']} ({scenario_type})")
                else:
                    scenario_type = 'RANDOM'
                    v_rate = get_setting('mock_volatility_rate', 0.8)
                    params = {"volatility": float(v_rate)}

            # 2. 가격 업데이트 로직
            vol_val = params.get('volatility', 0.8)
            volatility = float(vol_val) / 100.0
            
            with get_db_connection() as conn:
                cursor = conn.execute('SELECT p.code, p.current, s.base_price FROM mock_prices p JOIN mock_stocks s ON p.code = s.code')
                updates = []
                
                elapsed = now - self.scenario_start_time
                
                for code, current, base_price in cursor.fetchall():
                    # 시나리오별 가중치 계산
                    bias = 0
                    if scenario_type == 'V_SHAPE':
                        duration = params.get('duration', 3600)
                        drop = params.get('drop', -10.0) / 100.0
                        recovery = params.get('recovery', 12.0) / 100.0
                        
                        if elapsed < duration / 2: # 하락 국면
                            bias = drop / (duration / 2)
                        else: # 반등 국면
                            bias = recovery / (duration / 2)
                            
                    elif scenario_type == 'BEAR':
                        drop = params.get('drop', -20.0) / 100.0
                        duration = params.get('duration', 7200)
                        bias = drop / duration
                        
                    change = random.uniform(-volatility, volatility) + bias
                    new_price = int(current * (1 + change))
                    
                    # 상하한가 ±30% 제한
                    new_price = max(int(base_price * 0.7), min(int(base_price * 1.3), new_price))
                    updates.append((new_price, datetime.now().isoformat(), code))
                
                conn.executemany('UPDATE mock_prices SET current = ?, last_update = ? WHERE code = ?', updates)
                conn.commit()
        except Exception as e:
            logger.error(f"🎮 Mock 가격 업데이트 실패: {e}")

    def get_token(self) -> Optional[str]:
        return self.token

    def get_balance(self, token: str) -> Tuple[int, int, int]:
        try:
            with get_db_connection() as conn:
                acc_row = conn.execute('SELECT cash FROM mock_account WHERE id=1').fetchone()
                cash = acc_row['cash'] if acc_row else 0
                
                # 보유 주식 평가
                holdings_val = 0
                cursor = conn.execute('''
                    SELECT h.qty, p.current 
                    FROM mock_holdings h 
                    JOIN mock_prices p ON h.code = p.code 
                    WHERE h.qty > 0
                ''')
                for qty, current in cursor.fetchall():
                    holdings_val += qty * current
                
                total_eval = cash + holdings_val
                # [Optimization] 매번 찍히는 잔고 로그를 debug로 변경하여 로그 폭주 방지
                logger.debug(f"🎮 Mock 계좌 잔고 - 현금: {cash:,}, 보유평가: {holdings_val:,}, 총평가: {total_eval:,}")
                return cash, total_eval, cash
        except Exception as e:
            logger.error(f"🎮 Mock 잔고 조회 실패: {e}")
            return 0, 0, 0

    def get_total_eval_amt(self, token: str) -> int:
        """총 평가 금액 조회"""
        _, total_eval, _ = self.get_balance(token)
        return total_eval

    def get_account_data(self, token: str) -> Tuple[List[Dict], Dict]:
        self._update_prices()
        stock_list = []
        total_eval = 0
        total_pl = 0
        
        try:
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT h.code, s.name, h.qty, h.avg_price, p.current, h.current_price as last_h_price, h.source
                    FROM mock_holdings h
                    LEFT JOIN mock_stocks s ON h.code = s.code
                    LEFT JOIN mock_prices p ON h.code = p.code
                    WHERE h.qty > 0
                ''')
                for row in cursor.fetchall():
                    code = row['code']
                    name = row['name'] or code # 이름 없으면 코드로 표시
                    qty = row['qty']
                    avg_price = row['avg_price']
                    current = row['current'] if row['current'] is not None else row['last_h_price']
                    source = row['source'] if 'source' in row.keys() and row['source'] else '조건식' # 기본값
                    
                    buy_amt = int(qty * avg_price)
                    eval_amt = int(qty * current)
                    pl = eval_amt - buy_amt
                    pl_rt = (pl / buy_amt * 100) if buy_amt > 0 else 0
                    
                    stock_list.append({
                        "stk_cd": code,
                        "stk_nm": name,
                        "rmnd_qty": str(qty),
                        "cur_prc": str(current),
                        "pchs_avg_pric": str(int(avg_price)),
                        "pchs_amt": str(buy_amt),
                        "evlu_amt": str(eval_amt),
                        "pl_amt": str(pl),
                        "pl_rt": f"{pl_rt:.2f}",
                        "trade_type": source # [UI 표시용]
                    })
                    total_eval += eval_amt
                    total_pl += pl
                    
                summary = {
                    "stk_acnt_evlt_prst": stock_list,
                    "tot_evlu_amt": str(total_eval),
                    "tdy_lspft_amt": str(total_pl)
                }
                return stock_list, summary
        except Exception as e:
            logger.error(f"🎮 Mock 계좌 데이터 조회 실패: {e}")
            return [], {}

    def get_my_stocks(self, token: str, print_df: bool = False) -> List[Dict]:
        stocks, _ = self.get_account_data(token)
        return stocks

    def buy_stock(self, stk_cd: str, ord_qty: str, ord_uv: str, token: str, source: str = '검색식') -> Tuple[str, str]:
        try:
            qty = int(ord_qty)
            price = int(ord_uv)
            self._update_prices()
            
            actual_price = 0
            actual_name = stk_cd
            
            with get_db_connection() as conn:
                acc = conn.execute('SELECT cash FROM mock_account WHERE id=1').fetchone()
                cash = acc['cash']
                
                order_amt = qty * price
                if cash < order_amt:
                    return "INSUFFICIENT_BALANCE", "잔고 부족"
                
                # [Fix] 종목 없을 경우 생성 시도
                p_row = conn.execute('SELECT current FROM mock_prices WHERE code=?', (stk_cd,)).fetchone()
                if not p_row:
                    new_base = random.randint(100, 500) * 100
                    conn.execute('INSERT OR IGNORE INTO mock_stocks (code, name, base_price) VALUES (?, ?, ?)', (stk_cd, f"Test_{stk_cd}", new_base))
                    conn.execute('INSERT OR IGNORE INTO mock_prices (code, current, last_update) VALUES (?, ?, datetime("now"))', (stk_cd, new_base))
                    p_row = {'current': new_base}
                
                # 1. 실제 가격에 슬리피지(Slippage) 적용
                slippage_rate = float(get_setting('mock_slippage_rate', 0.05)) / 100.0
                actual_price = int(p_row['current'] * (1 + slippage_rate))
                
                actual_amt = qty * actual_price
                
                # 계좌 차감
                conn.execute('UPDATE mock_account SET cash = cash - ? WHERE id=1', (actual_amt,))
                
                # [Root Fix] 보유 종목 업데이트 시 source(검색식/모델)를 필수로 저장
                h_row = conn.execute('SELECT qty, avg_price FROM mock_holdings WHERE code=?', (stk_cd,)).fetchone()
                if h_row:
                    new_qty = h_row['qty'] + qty
                    new_avg = (h_row['qty'] * h_row['avg_price'] + actual_amt) / new_qty
                    # 기존 UPDATE 문에 source=? 추가
                    conn.execute('UPDATE mock_holdings SET qty=?, avg_price=?, updated_at=datetime("now"), source=? WHERE code=?', (new_qty, new_avg, source, stk_cd))
                else:
                    # 기존 INSERT 문에 source 추가 확인
                    conn.execute('INSERT INTO mock_holdings (code, qty, avg_price, current_price, updated_at, source) VALUES (?, ?, ?, ?, datetime("now"), ?)', (stk_cd, qty, actual_price, actual_price, source))
                
                s_row = conn.execute('SELECT name FROM mock_stocks WHERE code=?', (stk_cd,)).fetchone()
                if s_row: actual_name = s_row['name']
                
                conn.commit()
            
            # [미체결 주문 추적] 주문을 미체결 목록에 추가 (랜덤 대기 시간: 0.2~0.8초)
            import threading
            order_no = f"MOCK_{self.order_counter}"
            self.order_counter += 1
            
            order = {
                'stk_cd': stk_cd,
                'code': stk_cd,
                'name': actual_name,
                'qty': qty,
                'price': actual_price,
                'type': 'buy',
                'ord_tp': '01',
                'ord_no': order_no,
                'org_ord_no': order_no,
                'timestamp': time.time()
            }
            self.outstanding_orders.append(order)
            
            conn.commit()
            
            # [Fix] 즉시 업데이트를 위해 가격 및 계좌 데이터 리프레시 강제 호출
            self._update_prices(force=True)
            
            return "SUCCESS", "체결 완료"
        except Exception as e:
            logger.error(f"🎮 Mock 매수 실패: {e}")
            return "ERROR", str(e)

    def sell_stock(self, stk_cd: str, ord_qty: str, token: str) -> Tuple[str, str]:
        try:
            qty = int(ord_qty)
            self._update_prices()
            
            actual_price = 0
            actual_name = stk_cd
            avg_price = 0
            
            with get_db_connection() as conn:
                h_row = conn.execute('SELECT qty, avg_price, current_price FROM mock_holdings WHERE code=?', (stk_cd,)).fetchone()
                if not h_row or h_row['qty'] < qty:
                    return "INSUFFICIENT_QTY", "수량 부족"
                
                avg_price = h_row['avg_price']
                p_row = conn.execute('SELECT current FROM mock_prices WHERE code=?', (stk_cd,)).fetchone()
                
                if p_row:
                    # 매도 시에는 현재가보다 조금 싸게(0.05%) 체결됨 (슬리피지)
                    slippage_rate = float(get_setting('mock_slippage_rate', 0.05)) / 100.0
                    actual_price = int(p_row['current'] * (1 - slippage_rate))
                else:
                    actual_price = h_row['current_price']
                
                gross_amt = qty * actual_price
                
                # [내년 세금 반영] 매도 세금/수수료 0.3% 적용
                tax_rate = float(get_setting('mock_tax_rate', 0.3)) / 100.0
                tax_amt = int(gross_amt * tax_rate)
                actual_amt = gross_amt - tax_amt
                
                # 계좌 가산
                conn.execute('UPDATE mock_account SET cash = cash + ? WHERE id=1', (actual_amt,))
                
                # 보유 종목 업데이트
                if h_row['qty'] == qty:
                    conn.execute('DELETE FROM mock_holdings WHERE code=?', (stk_cd,))
                else:
                    conn.execute('UPDATE mock_holdings SET qty = qty - ? WHERE code=?', (qty, stk_cd))
                
                s_row = conn.execute('SELECT name FROM mock_stocks WHERE code=?', (stk_cd,)).fetchone()
                if s_row: actual_name = s_row['name']
                
                conn.commit()
                logger.info(f"🎮 Mock 매도 계산 - 거래금액: {gross_amt:,}원, 세금(0.3%): {tax_amt:,}원, 최종입금: {actual_amt:,}원")
                
            # [미체결 주문 추적] 매도 주문을 미체결 목록에 추가 (0.5초 후 자동 체결)
            import threading
            order_no = f"MOCK_{self.order_counter}"
            self.order_counter += 1
            
            order = {
                'stk_cd': stk_cd,
                'code': stk_cd,
                'name': actual_name,
                'qty': qty,
                'price': actual_price,
                'type': 'sell',
                'ord_tp': '02',
                'ord_no': order_no,
                'org_ord_no': order_no,
                'timestamp': time.time()
            }
            self.outstanding_orders.append(order)
            logger.info(f"🎮 Mock 미체결 추가: {stk_cd} 매도 {qty}주 (주문번호: {order_no})")
            
            # 0.5초 후 자동 체결 (미체결 목록에서 제거)
            # [Fix] 즉시 업데이트 강제 호출
            self._update_prices(force=True)
            
            profit_rate = (actual_price / avg_price - 1) * 100 if avg_price > 0 else 0
            logger.info(f"🎮 Mock 매도 성공: {stk_cd} {qty}주 @ {actual_price:,}원 ({profit_rate:+.2f}%)")
            return "SUCCESS", "체결 완료"
        except Exception as e:
            logger.error(f"🎮 Mock 매도 실패: {e}")
            return "ERROR", str(e)

    def get_current_price(self, stk_cd: str, token: str) -> Optional[dict]:
        self._update_prices()
        try:
            with get_db_connection() as conn:
                row = conn.execute('''
                    SELECT p.current, s.base_price, s.name 
                    FROM mock_prices p 
                    JOIN mock_stocks s ON p.code = s.code 
                    WHERE p.code = ?
                ''', (stk_cd,)).fetchone()
                
                if not row:
                    new_base = random.randint(100, 500) * 100
                    new_current = new_base
                    conn.execute('INSERT OR IGNORE INTO mock_stocks (code, name, base_price) VALUES (?, ?, ?)', (stk_cd, f"Test_{stk_cd}", new_base))
                    conn.execute('INSERT OR IGNORE INTO mock_prices (code, current, last_update) VALUES (?, ?, datetime("now"))', (stk_cd, new_current))
                    conn.commit()
                    cur = new_current
                    base = new_base
                else:
                    cur = row['current']
                    base = row['base_price']

                return {
                    'stk_cd': stk_cd,
                    'stk_prpr': str(cur),
                    'prdy_vrss': str(cur - base),
                    'prdy_ctrt': f"{(cur/base-1)*100:.2f}",
                    'sel_fpr_bid': str(cur),
                    'sel_fpr_ask': str(cur)
                }
        except: pass
        return {
            'stk_cd': stk_cd,
            'stk_prpr': '10000',
            'prdy_vrss': '0',
            'prdy_ctrt': '0.00',
            'sel_fpr_bid': '10000',
            'sel_fpr_ask': '10000'
        }

    def get_outstanding_orders(self, token: str) -> List[Dict]:
        """미체결 주문 조회 (Mock)"""
        # 오래된 주문 자동 정리 (5초 이상 경과한 주문)
        current_time = time.time()
        self.outstanding_orders = [
            order for order in self.outstanding_orders 
            if current_time - order.get('timestamp', 0) < 5
        ]
        
        if self.outstanding_orders:
            logger.info(f"🎮 Mock 미체결 조회: {len(self.outstanding_orders)}개 주문")
        
        return self.outstanding_orders.copy()  # 복사본 반환

    def cancel_stock(self, stk_cd: str, qty: str, org_ord_no: str, token: str) -> Tuple[str, str]:
        """주문 취소 (Mock)"""
        try:
            # 주문번호로 미체결 주문 찾기
            for order in self.outstanding_orders:
                if order.get('ord_no') == org_ord_no or order.get('org_ord_no') == org_ord_no:
                    self.outstanding_orders.remove(order)
                    logger.info(f"🎮 Mock 주문 취소 성공: {stk_cd} {order.get('type')} {qty}주 (주문번호: {org_ord_no})")
                    return "SUCCESS", "취소 완료"
            
            logger.warning(f"🎮 Mock 주문 취소 실패: 주문번호 {org_ord_no} 찾을 수 없음")
            return "ERROR", "주문번호를 찾을 수 없습니다"
        except Exception as e:
            logger.error(f"🎮 Mock 주문 취소 오류: {e}")
            return "ERROR", str(e)
