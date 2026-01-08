"""
매매 로그 DB 관리 모듈
JSON 파일 대신 SQLite DB를 사용하여 안정성 향상
"""
import sqlite3
import datetime
import os
from logger import logger
from get_setting import get_setting

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def get_db_connection():
	"""DB 연결 생성"""
	conn = sqlite3.connect(DB_FILE, timeout=30)
	conn.execute('PRAGMA journal_mode=WAL')
	conn.row_factory = sqlite3.Row
	return conn

def log_buy_to_db(code, name, qty, price, mode=None):
	"""매수 로그 저장"""
	if mode is None:
		try:
			from kiwoom_adapter import get_current_api_mode
			mode = get_current_api_mode().upper()
		except:
			mode = "REAL"
	else:
		mode = str(mode).upper()
		
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	amt = qty * price
	
	# [Simulation Context] 현재 활성화된 시뮬레이션 정보 가져오기
	config_id = None
	scenario_id = None
	try:
		with get_db_connection() as conn:
			# 활성화된 시나리오 조회
			s_row = conn.execute('SELECT id FROM sim_scenarios WHERE is_active = 1 LIMIT 1').fetchone()
			if s_row: scenario_id = s_row['id']
			
			# 가장 최근의 시뮬레이션 설정(팩터) 조회
			c_row = conn.execute('SELECT id FROM sim_configs ORDER BY id DESC LIMIT 1').fetchone()
			if c_row: config_id = c_row['id']
	except: pass

	try:
		with get_db_connection() as conn:
			conn.execute('''
				INSERT INTO trades (timestamp, type, code, name, qty, price, amt, avg_price, mode, memo)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			''', (timestamp, 'buy', code, name, qty, price, amt, price, mode, 
				 f"SIM_CONFIG:{config_id}, SIM_SCENARIO:{scenario_id}" if config_id or scenario_id else ""))
			conn.commit()
			logger.info(f"✅ 매수 로그 DB 저장: {name} {qty}주 @ {price:,}원 [{mode}]" + 
						(f" (SIM:{config_id}/{scenario_id})" if config_id or scenario_id else ""))
	except Exception as e:
		logger.error(f"❌ 매수 로그 DB 저장 실패 ({name} @ {mode}): {e}")

def log_sell_to_db(code, name, qty, price, profit_rate, reason, mode=None):
	"""매도 로그 저장"""
	if mode is None:
		try:
			from kiwoom_adapter import get_current_api_mode
			mode = get_current_api_mode().upper()
		except:
			mode = "REAL"
	else:
		mode = str(mode).upper()
		
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	amt = qty * price
	
	# [Simulation Context] 현재 활성화된 시뮬레이션 정보 가져오기
	config_id = None
	scenario_id = None
	try:
		with get_db_connection() as conn:
			s_row = conn.execute('SELECT id FROM sim_scenarios WHERE is_active = 1 LIMIT 1').fetchone()
			if s_row: scenario_id = s_row['id']
			c_row = conn.execute('SELECT id FROM sim_configs ORDER BY id DESC LIMIT 1').fetchone()
			if c_row: config_id = c_row['id']
	except: pass

	try:
		with get_db_connection() as conn:
			conn.execute('''
				INSERT INTO trades (timestamp, type, code, name, qty, price, amt, profit_rate, reason, mode, memo)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			''', (timestamp, 'sell', code, name, qty, price, amt, profit_rate, reason, mode,
				 f"SIM_CONFIG:{config_id}, SIM_SCENARIO:{scenario_id}" if config_id or scenario_id else ""))
			conn.commit()
			logger.info(f"✅ 매도 로그 DB 저장: {name} {qty}주 @ {price:,}원 ({profit_rate:+.2f}%) [{mode}]" +
						(f" (SIM:{config_id}/{scenario_id})" if config_id or scenario_id else ""))
	except Exception as e:
		logger.error(f"❌ 매도 로그 DB 저장 실패 ({name} @ {mode}): {e}")

def get_trading_logs_from_db(mode=None, limit=10000, since_id=0, date=None):
	"""
	DB에서 매매 로그 조회 (증분 조회 지원)
	
	Args:
		mode: 'MOCK' 또는 'REAL' (None이면 모두 조회)
		limit: 최대 조회 개수
		since_id: 이 ID보다 큰 기록만 조회 (0이면 최신순 limit개)
		date: 특정 날짜(YYYY-MM-DD) 필터 (None이면 날짜 제한 없음)
	"""
	try:
		with get_db_connection() as conn:
			# 조건절 구성
			conditions = []
			params_buy = []
			
			conditions.append("type = 'buy' COLLATE NOCASE")
			
			if mode:
				conditions.append("mode = ?")
				params_buy.append(mode)
				
			if date:
				conditions.append("timestamp LIKE ?")
				params_buy.append(f"{date}%")
				
			if since_id > 0:
				conditions.append("id > ?")
				params_buy.append(since_id)
				
			where_clause = "WHERE " + " AND ".join(conditions)
			params_buy.append(limit)
			
			# 매수 로그 조회
			cursor = conn.execute(f'''
				SELECT id, timestamp as time, code as stk_cd, name as stk_nm, 
				       qty, price, amt, avg_price, mode
				FROM trades 
				{where_clause}
				ORDER BY id DESC 
				LIMIT ?
			''', tuple(params_buy))
			
			buys = []
			for row in cursor.fetchall():
				buys.append({
					'id': row['id'],
					'time': row['time'],
					'stk_cd': row['stk_cd'],
					'stk_nm': row['stk_nm'],
					'name': row['stk_nm'],
					'qty': row['qty'],
					'price': row['price'],
					'avg_price': row['avg_price'],
					'amt': row['amt'],
					'mode': row['mode']
				})
			
			# 매도 로그 조회 (같은 로직 적용)
			conditions_sell = []
			params_sell = []
			
			conditions_sell.append("type = 'sell' COLLATE NOCASE")
			
			if mode:
				conditions_sell.append("mode = ?")
				params_sell.append(mode)

			if date:
				conditions_sell.append("timestamp LIKE ?")
				params_sell.append(f"{date}%")
				
			if since_id > 0:
				conditions_sell.append("id > ?")
				params_sell.append(since_id)
				
			where_clause_sell = "WHERE " + " AND ".join(conditions_sell)
			params_sell.append(limit)
			
			cursor = conn.execute(f'''
				SELECT id, timestamp as time, code as stk_cd, name as stk_nm,
				       qty, price, amt, profit_rate, reason, mode
				FROM trades 
				{where_clause_sell}
				ORDER BY id DESC 
				LIMIT ?
			''', tuple(params_sell))
			
			sells = []
			for row in cursor.fetchall():
				sells.append({
					'id': row['id'],
					'time': row['time'],
					'stk_cd': row['stk_cd'],
					'stk_nm': row['stk_nm'],
					'name': row['stk_nm'],
					'qty': row['qty'],
					'price': row['price'],
					'amt': row['amt'],
					'yield': row['profit_rate'],
					'profit_rate': row['profit_rate'],
					'reason': row['reason'] or '',
					'mode': row['mode']
				})
			
			return {'buys': buys, 'sells': sells}
			
	except Exception as e:
		logger.error(f"❌ 매매 로그 DB 조회 실패: {e}")
		return {'buys': [], 'sells': []}

def get_today_trading_stats(mode=None):
	"""
	오늘의 매매 통계 조회
	
	Returns:
		{'total_trades': int, 'win_count': int, 'total_profit': float}
	"""
	today = datetime.datetime.now().strftime('%Y-%m-%d')
	
	try:
		with get_db_connection() as conn:
			if mode:
				where_clause = "WHERE type = 'sell' COLLATE NOCASE AND mode = ? AND timestamp LIKE ?"
				params = (mode, f"{today}%")
			else:
				where_clause = "WHERE type = 'sell' COLLATE NOCASE AND timestamp LIKE ?"
				params = (f"{today}%",)
			
			cursor = conn.execute(f'''
				SELECT COUNT(*) as total,
				       SUM(CASE WHEN profit_rate > 0 THEN 1 ELSE 0 END) as wins,
				       SUM(amt * profit_rate / 100.0 / (1 + profit_rate / 100.0)) as total_profit,
				       AVG(profit_rate) as avg_profit
				FROM trades
				{where_clause}
			''', params)
			
			row = cursor.fetchone()
			return {
				'total': row['total'] or 0,
				'wins': row['wins'] or 0,
				'total_profit': row['total_profit'] or 0.0,
				'avg_profit': row['avg_profit'] or 0.0
			}
	except Exception as e:
		logger.error(f"❌ 매매 통계 조회 실패: {e}")
		return {'total': 0, 'wins': 0, 'total_profit': 0.0}

def clear_old_trades(days=30):
	"""오래된 매매 로그 삭제 (DB 용량 관리)"""
	cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
	
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('''
				DELETE FROM trades WHERE timestamp < ?
			''', (cutoff_date,))
			deleted = cursor.rowcount
			conn.commit()
			logger.info(f"✅ {days}일 이전 매매 로그 {deleted}건 삭제")
			return deleted
	except Exception as e:
		logger.error(f"❌ 오래된 로그 삭제 실패: {e}")
		return 0

def delete_stock_trades(code, mode=None):
	"""특정 종목의 오늘 매매 기록 삭제 (초기화용)"""
	today = datetime.datetime.now().strftime('%Y-%m-%d')
	try:
		with get_db_connection() as conn:
			# [중요] 매도 기록(sell)은 남기고, 매수 기록(buy)만 삭제하여 초기화
			query = "DELETE FROM trades WHERE code = ? AND timestamp LIKE ? AND type = 'buy'"
			params = [code, f"{today}%"]
			
			if mode:
				query += " AND mode = ?"
				params.append(mode)
				
			cursor = conn.execute(query, tuple(params))
			conn.commit()
			if cursor.rowcount > 0:
				logger.info(f"✅ {code} 매수 기록 초기화 완료 (재진입 준비, {cursor.rowcount}건 삭제)")
	except Exception as e:
		logger.error(f"❌ {code} 매매 기록 삭제 실패: {e}")
