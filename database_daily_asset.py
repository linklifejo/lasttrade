"""
일일 자산 기록 DB 헬퍼
daily_asset_*.json 파일을 DB로 대체
"""
import sqlite3
import datetime
import json
import os
from logger import logger

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def get_db_connection():
	"""DB 연결 생성"""
	conn = sqlite3.connect(DB_FILE, timeout=30)
	conn.execute('PRAGMA journal_mode=WAL')
	conn.row_factory = sqlite3.Row
	return conn

def save_daily_asset(asset, mode='MOCK'):
	"""일일 자산 저장"""
	today = datetime.datetime.now().strftime('%Y-%m-%d')
	
	try:
		with get_db_connection() as conn:
			# 오늘 날짜 데이터가 있으면 업데이트, 없으면 삽입
			conn.execute('''
				INSERT OR REPLACE INTO daily_assets (date, asset, mode)
				VALUES (?, ?, ?)
			''', (today, asset, mode))
			conn.commit()
			logger.info(f"일일 자산 저장: {asset:,}원 [{mode}]")
	except Exception as e:
		logger.error(f"일일 자산 저장 실패: {e}")

def get_daily_asset(mode='MOCK'):
	"""오늘의 자산 조회"""
	today = datetime.datetime.now().strftime('%Y-%m-%d')
	
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('''
				SELECT asset FROM daily_assets 
				WHERE date = ? AND mode = ?
			''', (today, mode))
			row = cursor.fetchone()
			if row:
				return row['asset']
			return None
	except Exception as e:
		logger.error(f"일일 자산 조회 실패: {e}")
		return None

def get_all_daily_assets(mode='MOCK', days=30):
	"""최근 N일간의 자산 기록 조회"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('''
				SELECT date, asset FROM daily_assets 
				WHERE mode = ?
				ORDER BY date DESC
				LIMIT ?
			''', (mode, days))
			
			return [{'date': row['date'], 'asset': row['asset']} for row in cursor.fetchall()]
	except Exception as e:
		logger.error(f"일일 자산 기록 조회 실패: {e}")
		return []

def migrate_daily_asset_json():
	"""daily_asset_*.json 파일을 DB로 마이그레이션"""
	base_dir = os.path.dirname(os.path.abspath(__file__))
	
	files = [
		('daily_asset_mock.json', 'MOCK'),
		('daily_asset_real.json', 'REAL')
	]
	
	for filename, mode in files:
		filepath = os.path.join(base_dir, filename)
		
		if not os.path.exists(filepath):
			continue
		
		try:
			with open(filepath, 'r', encoding='utf-8') as f:
				data = json.load(f)
			
			date = data.get('date')
			asset = data.get('asset', 0)
			
			if date and asset:
				with get_db_connection() as conn:
					conn.execute('''
						INSERT OR REPLACE INTO daily_assets (date, asset, mode)
						VALUES (?, ?, ?)
					''', (date, asset, mode))
					conn.commit()
				
				logger.info(f"✅ {filename} 마이그레이션 완료")
				
				# 백업
				os.rename(filepath, filepath + '.backup')
		except Exception as e:
			logger.error(f"{filename} 마이그레이션 실패: {e}")
