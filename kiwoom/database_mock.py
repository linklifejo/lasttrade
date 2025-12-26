"""
Mock 서버 데이터를 JSON에서 DB로 완전히 전환
모든 Mock 데이터를 DB에서 관리
"""
import sqlite3
import json
import os
import datetime
from logger import logger

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trading.db')

def get_db_connection():
	conn = sqlite3.connect(DB_FILE)
	conn.row_factory = sqlite3.Row
	return conn

# ==================== Mock 계좌 ====================

def get_mock_account():
	"""Mock 계좌 정보 조회"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT cash, total_eval FROM mock_account WHERE id = 1')
			row = cursor.fetchone()
			if row:
				return {'cash': row['cash'], 'total_eval': row['total_eval']}
			# 기본값
			return {'cash': 20000000, 'total_eval': 20000000}
	except:
		return {'cash': 20000000, 'total_eval': 20000000}

def update_mock_account(cash, total_eval):
	"""Mock 계좌 정보 업데이트"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	try:
		with get_db_connection() as conn:
			conn.execute('''
				INSERT OR REPLACE INTO mock_account (id, cash, total_eval, updated_at)
				VALUES (1, ?, ?, ?)
			''', (cash, total_eval, timestamp))
			conn.commit()
	except Exception as e:
		logger.error(f"Mock 계좌 업데이트 실패: {e}")

# ==================== Mock 보유 종목 ====================

def get_mock_holdings():
	"""Mock 보유 종목 조회"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT code, qty, avg_price, current_price FROM mock_holdings')
			holdings = {}
			for row in cursor.fetchall():
				holdings[row['code']] = {
					'qty': row['qty'],
					'avg_price': row['avg_price'],
					'current_price': row['current_price']
				}
			return holdings
	except:
		return {}

def update_mock_holding(code, qty, avg_price, current_price):
	"""Mock 보유 종목 업데이트"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	try:
		with get_db_connection() as conn:
			if qty > 0:
				conn.execute('''
					INSERT OR REPLACE INTO mock_holdings (code, qty, avg_price, current_price, updated_at)
					VALUES (?, ?, ?, ?, ?)
				''', (code, qty, avg_price, current_price, timestamp))
			else:
				conn.execute('DELETE FROM mock_holdings WHERE code = ?', (code,))
			conn.commit()
	except Exception as e:
		logger.error(f"Mock 보유 종목 업데이트 실패: {e}")

# ==================== Mock 종목 정보 ====================

def get_mock_stock_info(code):
	"""Mock 종목 정보 조회"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT name, base_price FROM mock_stocks WHERE code = ?', (code,))
			row = cursor.fetchone()
			if row:
				return {'name': row['name'], 'base_price': row['base_price']}
	except:
		pass
	return None

def get_all_mock_stocks():
	"""모든 Mock 종목 조회"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT code, name, base_price FROM mock_stocks')
			stocks = {}
			for row in cursor.fetchall():
				stocks[row['code']] = {
					'name': row['name'],
					'base_price': row['base_price']
				}
			return stocks
	except:
		return {}

# ==================== Mock 가격 ====================

def get_mock_price(code):
	"""Mock 가격 조회"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT current, open, high, low FROM mock_prices WHERE code = ?', (code,))
			row = cursor.fetchone()
			if row:
				return {
					'current': row['current'],
					'open': row['open'],
					'high': row['high'],
					'low': row['low']
				}
	except:
		pass
	return None

def update_mock_price(code, current, open_price, high, low):
	"""Mock 가격 업데이트"""
	timestamp = datetime.datetime.now().isoformat()
	try:
		with get_db_connection() as conn:
			conn.execute('''
				INSERT OR REPLACE INTO mock_prices (code, current, open, high, low, last_update)
				VALUES (?, ?, ?, ?, ?, ?)
			''', (code, current, open_price, high, low, timestamp))
			conn.commit()
	except Exception as e:
		logger.error(f"Mock 가격 업데이트 실패: {e}")

# ==================== 마이그레이션 ====================

def migrate_mock_data_to_db():
	"""Mock JSON 파일들을 DB로 마이그레이션"""
	base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kiwoom', 'mock_data')
	
	# 1. stocks.json
	stocks_file = os.path.join(base_dir, 'stocks.json')
	if os.path.exists(stocks_file):
		try:
			with open(stocks_file, 'r', encoding='utf-8') as f:
				stocks = json.load(f)
			
			with get_db_connection() as conn:
				for code, info in stocks.items():
					conn.execute('''
						INSERT OR REPLACE INTO mock_stocks (code, name, base_price)
						VALUES (?, ?, ?)
					''', (code, info['name'], info['base_price']))
				conn.commit()
			
			logger.info(f"✅ stocks.json 마이그레이션 완료: {len(stocks)}개")
			os.rename(stocks_file, stocks_file + '.backup')
		except Exception as e:
			logger.error(f"stocks.json 마이그레이션 실패: {e}")
	
	# 2. account.json
	account_file = os.path.join(base_dir, 'account.json')
	if os.path.exists(account_file):
		try:
			with open(account_file, 'r', encoding='utf-8') as f:
				account = json.load(f)
			
			update_mock_account(account['cash'], account.get('total_eval', account['cash']))
			
			# 보유 종목
			for code, holding in account.get('holdings', {}).items():
				update_mock_holding(code, holding['qty'], holding['avg_price'], holding.get('current_price', holding['avg_price']))
			
			logger.info(f"✅ account.json 마이그레이션 완료")
			os.rename(account_file, account_file + '.backup')
		except Exception as e:
			logger.error(f"account.json 마이그레이션 실패: {e}")
	
	# 3. prices.json
	prices_file = os.path.join(base_dir, 'prices.json')
	if os.path.exists(prices_file):
		try:
			with open(prices_file, 'r', encoding='utf-8') as f:
				prices = json.load(f)
			
			with get_db_connection() as conn:
				for code, price_info in prices.items():
					conn.execute('''
						INSERT OR REPLACE INTO mock_prices (code, current, open, high, low, last_update)
						VALUES (?, ?, ?, ?, ?, ?)
					''', (code, price_info['current'], price_info['open'], price_info['high'], price_info['low'], price_info.get('last_update', datetime.datetime.now().isoformat())))
				conn.commit()
			
			logger.info(f"✅ prices.json 마이그레이션 완료: {len(prices)}개")
			os.rename(prices_file, prices_file + '.backup')
		except Exception as e:
			logger.error(f"prices.json 마이그레이션 실패: {e}")
	
	# 4. orders.json은 이미 trades 테이블로 마이그레이션됨
	orders_file = os.path.join(base_dir, 'orders.json')
	if os.path.exists(orders_file):
		logger.info("✅ orders.json은 이미 trades 테이블로 마이그레이션됨, 백업만 생성")
		try:
			os.rename(orders_file, orders_file + '.backup')
		except:
			pass
	
	logger.info("🎉 모든 Mock 데이터 마이그레이션 완료!")
