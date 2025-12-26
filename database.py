import aiosqlite
import asyncio
import datetime
import os
from logger import logger
import config

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

async def init_db():
	"""데이터베이스 및 테이블 초기화"""
	async with aiosqlite.connect(DB_FILE) as db:
		# 매매 기록 테이블 (Enhanced for trading_log replacement)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS trades (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				timestamp TEXT NOT NULL,
				type TEXT NOT NULL,
				code TEXT NOT NULL,
				name TEXT,
				qty INTEGER,
				price REAL,
				profit_rate REAL,
				memo TEXT,
				mode TEXT DEFAULT 'REAL',
				reason TEXT,
				amt REAL,
				avg_price REAL
			)
		''')
		
		# 종목별 상태 테이블 (트레일링 스탑용 고점 기록)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS stock_status (
				code TEXT PRIMARY KEY,
				high_price REAL DEFAULT 0,
				updated_at TEXT
			)
		''')

		# 자산 히스토리 테이블 (차트용)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS asset_history (
				timestamp TEXT PRIMARY KEY,
				total_asset INTEGER,
				profit_loss INTEGER
			)
		''')

		# 가격 히스토리 테이블 (RSI 계산용, 1분봉 데이터 축적)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS price_history (
				code TEXT,
				timestamp TEXT,
				price INTEGER,
				PRIMARY KEY (code, timestamp)
			)
		''')
		
		# 보유 시간 추적 테이블 (held_times.json 대체)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS held_times (
				code TEXT PRIMARY KEY,
				held_since REAL NOT NULL,
				updated_at TEXT
			)
		''')
		
		# 설정 저장 테이블 (settings.json 대체)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS settings (
				key TEXT PRIMARY KEY,
				value TEXT NOT NULL,
				updated_at TEXT
			)
		''')
		
		# 일일 자산 기록 테이블 (daily_asset_*.json 대체)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS daily_assets (
				date TEXT NOT NULL,
				asset INTEGER NOT NULL,
				mode TEXT DEFAULT 'REAL',
				PRIMARY KEY (date, mode)
			)
		''')
		
		# Mock 계좌 정보 테이블
		await db.execute('''
			CREATE TABLE IF NOT EXISTS mock_account (
				id INTEGER PRIMARY KEY CHECK (id = 1),
				cash INTEGER NOT NULL,
				total_eval INTEGER NOT NULL,
				updated_at TEXT
			)
		''')
		
		# Mock 보유 종목 테이블
		await db.execute('''
			CREATE TABLE IF NOT EXISTS mock_holdings (
				code TEXT PRIMARY KEY,
				qty INTEGER NOT NULL,
				avg_price REAL NOT NULL,
				current_price REAL NOT NULL,
				updated_at TEXT
			)
		''')
		
		# Mock 종목 정보 테이블
		await db.execute('''
			CREATE TABLE IF NOT EXISTS mock_stocks (
				code TEXT PRIMARY KEY,
				name TEXT NOT NULL,
				base_price INTEGER NOT NULL
			)
		''')
		
		# 실시간 상태 테이블 (모드별 분리 저장)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS system_status (
				api_mode TEXT PRIMARY KEY,
				status_json TEXT NOT NULL,
				updated_at TEXT
			)
		''')
		
		# 웹 명령 테이블 (web_command.json 대체)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS web_commands (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				command TEXT NOT NULL,
				params TEXT,
				status TEXT DEFAULT 'pending', -- pending, processing, completed
				timestamp TEXT NOT NULL
			)
		''')
		
# Simulation 관련 테이블 추가
		# 1. 시뮬레이션 설정 (팩터 데이터 세트)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS sim_configs (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				description TEXT,
				factors_json TEXT NOT NULL, -- RSI 기준, 매수비중 등 모든 팩터가 JSON으로 저장됨
				updated_at TEXT
			)
		''')

		# 2. 시나리오 데이터 (시장 상황 시나리오)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS sim_scenarios (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL, -- 예: 'V자 반등', '계단식 하락'
				type TEXT NOT NULL, -- CRASH, TREND, SIDEWAYS 등
				params_json TEXT NOT NULL, -- 변동성, 하락폭 등 시나리오 파라미터
				is_active INTEGER DEFAULT 0
			)
		''')

		# 3. 시뮬레이션 성적표 (학습용 결과 데이타)
		await db.execute('''
			CREATE TABLE IF NOT EXISTS sim_performance (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				config_id INTEGER,
				scenario_id INTEGER,
				start_time TEXT,
				end_time TEXT,
				total_return REAL,
				mdd REAL,
				win_rate REAL,
				trade_count INTEGER,
				performance_json TEXT, -- 구체적인 세부 지표들
				FOREIGN KEY (config_id) REFERENCES sim_configs(id),
				FOREIGN KEY (scenario_id) REFERENCES sim_scenarios(id)
			)
		''')

		# 4. 기본 시뮬레이션 시나리오 초기 데이터 삽입
		await db.execute('''
			INSERT OR IGNORE INTO sim_scenarios (id, name, type, params_json, is_active)
			VALUES (1, '기본(랜덤)', 'RANDOM', '{"volatility": 0.8}', 1)
		''')
		await db.execute('''
			INSERT OR IGNORE INTO sim_scenarios (id, name, type, params_json, is_active)
			VALUES (2, 'V자 반등(급락 후 복구)', 'V_SHAPE', '{"drop": -10.0, "duration": 3600, "recovery": 12.0}', 0)
		''')
		await db.execute('''
			INSERT OR IGNORE INTO sim_scenarios (id, name, type, params_json, is_active)
			VALUES (3, '폭락장(지속 하락)', 'BEAR', '{"drop": -20.0, "duration": 7200}', 0)
		''')

		await db.commit()
		logger.info(f"데이터베이스 초기화 완료: {DB_FILE}")

async def log_trade(trade_type, code, name, qty, price, profit_rate=0.0, memo="", mode="REAL", reason="", amt=0):
	"""매매 기록 저장 (Enhanced)"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	
	try:
		if mode == "REAL":
			if config.user_mock_setting: mode = "MOCK"
			elif config.is_paper_trading: mode = "PAPER"
	except: pass

	try:
		async with aiosqlite.connect(DB_FILE) as db:
			await db.execute('''
				INSERT INTO trades (timestamp, type, code, name, qty, price, profit_rate, memo, mode, reason, amt, avg_price)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			''', (timestamp, trade_type, code, name, qty, price, profit_rate, memo, mode, reason, amt, price))
			await db.commit()
	except Exception as e:
		logger.error(f"DB 매매 기록 저장 실패: {e}")

async def update_high_price(code, current_price):
	"""트레일링 스탑을 위한 종목별 최고가 갱신"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	try:
		async with aiosqlite.connect(DB_FILE) as db:
			# 현재 저장된 고점 확인
			cursor = await db.execute('SELECT high_price FROM stock_status WHERE code = ?', (code,))
			row = await cursor.fetchone()
			
			if row:
				prev_high = row[0]
				if current_price > prev_high:
					await db.execute('''
						UPDATE stock_status SET high_price = ?, updated_at = ? WHERE code = ?
					''', (current_price, timestamp, code))
					await db.commit()
					return True # 신규 고점 갱신
			else:
				# 데이터 없으면 새로 삽입
				# 데이터 없으면 새로 삽입 (OR IGNORE로 중복 에러 방지)
				await db.execute('''
					INSERT OR IGNORE INTO stock_status (code, high_price, updated_at) VALUES (?, ?, ?)
				''', (code, current_price, timestamp))
				await db.commit()
				return True
			return False
	except Exception as e:
		logger.error(f"DB 고점 갱신 실패: {e}")
		return False

async def get_high_price(code):
	"""종목별 최고가 조회"""
	try:
		async with aiosqlite.connect(DB_FILE) as db:
			cursor = await db.execute('SELECT high_price FROM stock_status WHERE code = ?', (code,))
			row = await cursor.fetchone()
			if row:
				return row[0]
			return 0
	except Exception as e:
		logger.error(f"DB 고점 조회 실패: {e}")
		return 0

async def get_recent_trades(limit=50):
	"""최근 매매 기록 조회"""
	try:
		async with aiosqlite.connect(DB_FILE) as db:
			db.row_factory = aiosqlite.Row
			cursor = await db.execute('''
				SELECT * FROM trades ORDER BY id DESC LIMIT ?
			''', (limit,))
			rows = await cursor.fetchall()
			return [dict(row) for row in rows]
	except Exception as e:
		logger.error(f"DB 매매 기록 조회 실패: {e}")
		return []

	except Exception as e:
		logger.error(f"DB 종목 상태 삭제 실패: {e}")

async def log_asset_history(total_asset, profit_loss):
	"""자산 변동 내역 저장"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') # 분 단위 저장
	try:
		async with aiosqlite.connect(DB_FILE) as db:
			await db.execute('''
				INSERT OR REPLACE INTO asset_history (timestamp, total_asset, profit_loss)
				VALUES (?, ?, ?)
			''', (timestamp, total_asset, profit_loss))
			await db.commit()
	except Exception as e:
		logger.error(f"DB 자산 기록 저장 실패: {e}")

async def log_price_history(code, price):
	"""종목별 가격(분봉) 저장"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M') # 분 단위
	try:
		async with aiosqlite.connect(DB_FILE) as db:
			await db.execute('''
				INSERT OR REPLACE INTO price_history (code, timestamp, price)
				VALUES (?, ?, ?)
			''', (code, timestamp, price))
			await db.commit()
	except Exception as e:
		logger.error(f"DB 가격 기록 저장 실패: {e}")

async def get_price_history(code, limit=30):
	"""RSI 계산용 가격 히스토리 조회"""
	try:
		async with aiosqlite.connect(DB_FILE) as db:
			cursor = await db.execute('''
				SELECT price FROM price_history 
				WHERE code = ? 
				ORDER BY timestamp ASC 
				LIMIT ?
			''', (code, limit))
			rows = await cursor.fetchall()
			return [row[0] for row in rows]
	except Exception as e:
		logger.error(f"DB 가격 기록 조회 실패: {e}")
		return []

import sqlite3

def get_db_connection():
	conn = sqlite3.connect(DB_FILE)
	conn.row_factory = sqlite3.Row
	return conn

def log_trade_sync(trade_type, code, name, qty, price, profit_rate=0.0, memo=""):
	"""매매 기록 저장 (Sync)"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	
	mode = "REAL"
	try:
		if config.user_mock_setting: mode = "MOCK"
		elif config.is_paper_trading: mode = "PAPER"
	except: pass

	try:
		with get_db_connection() as conn:
			conn.execute('''
				INSERT INTO trades (timestamp, type, code, name, qty, price, profit_rate, memo, mode)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
			''', (timestamp, trade_type, code, name, qty, price, profit_rate, memo, mode))
			conn.commit()
	except Exception as e:
		logger.error(f"DB 매매 기록 저장 실패(Sync): {e}")

def update_high_price_sync(code, current_price):
	"""트레일링 스탑을 위한 종목별 최고가 갱신 (Sync)"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT high_price FROM stock_status WHERE code = ?', (code,))
			row = cursor.fetchone()
			
			if row:
				prev_high = row['high_price']
				if current_price > prev_high:
					conn.execute('''
						UPDATE stock_status SET high_price = ?, updated_at = ? WHERE code = ?
					''', (current_price, timestamp, code))
					return True
			else:
				conn.execute('''
					INSERT OR IGNORE INTO stock_status (code, high_price, updated_at) VALUES (?, ?, ?)
				''', (code, current_price, timestamp))
				return True
			return False
	except Exception as e:
		logger.error(f"DB 고점 갱신 실패(Sync): {e}")
		return False

def get_high_price_sync(code):
	"""종목별 최고가 조회 (Sync)"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT high_price FROM stock_status WHERE code = ?', (code,))
			row = cursor.fetchone()
			if row:
				return row['high_price']
			return 0
	except Exception as e:
		logger.error(f"DB 고점 조회 실패(Sync): {e}")
		return 0

def clear_stock_status_sync(code):
	"""매도 후 종목 상태 초기화 (Sync)"""
	try:
		with get_db_connection() as conn:
			conn.execute('DELETE FROM stock_status WHERE code = ?', (code,))
			conn.commit()
	except Exception as e:
		logger.error(f"DB 종목 상태 삭제 실패(Sync): {e}")

def get_price_history_sync(code, limit=30):
	"""RSI 계산용 가격 히스토리 조회 (Sync)"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('''
				SELECT price FROM price_history 
				WHERE code = ? 
				ORDER BY timestamp ASC 
				LIMIT ?
			''', (code, limit))
			rows = cursor.fetchall()
			return [row['price'] for row in rows]
	except Exception as e:
		logger.error(f"DB 가격 기록 조회 실패(Sync): {e}")
		return []

