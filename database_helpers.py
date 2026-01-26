"""
통합 DB 헬퍼 모듈
모든 JSON 파일을 DB로 대체하는 헬퍼 함수들
"""
import sqlite3
import datetime
import json
import time
import math
from logger import logger
from pathlib import Path
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def get_db_connection():
	"""DB 연결 생성"""
	conn = None
	# [안정성 강화] DB Lock 발생 시 즉시 포기하지 않고 대기 (Busy Timeout 설정)
	# 최대 30초(30000ms) 동안 Lock이 풀리기를 기다리도록 설정
	# 또한, 연결 실패 시 5회까지 재시도
	max_retries = 5
	for attempt in range(max_retries):
		try:
			conn = sqlite3.connect(DB_FILE)
			conn.row_factory = sqlite3.Row
			# [Critical] WAL 모드 활성화 (읽기/쓰기 충돌 방지)
			conn.execute("PRAGMA journal_mode=WAL")
			# Busy Timeout 설정 (30초 대기)
			conn.execute("PRAGMA busy_timeout = 30000")
			return conn
		except sqlite3.OperationalError as e:
			if "locked" in str(e) and attempt < max_retries - 1:
				time.sleep(0.5) # 0.5초 대기 후 재시도
				continue
			raise e
	return conn

# ==================== Held Times ====================

def save_held_time(code, held_since=None):
	"""보유 시간 저장 (held_times.json 대체)"""
	if held_since is None:
		held_since = time.time()
	
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	
	try:
		with get_db_connection() as conn:
			conn.execute('''
				INSERT OR REPLACE INTO held_times (code, held_since, updated_at)
				VALUES (?, ?, ?)
			''', (code, held_since, timestamp))
			conn.commit()
	except Exception as e:
		logger.error(f"보유 시간 저장 실패: {e}")

def get_held_time(code):
	"""특정 종목의 보유 시작 시간 조회"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT held_since FROM held_times WHERE code = ?', (code,))
			row = cursor.fetchone()
			if row:
				return row['held_since']
			return None
	except Exception as e:
		logger.error(f"보유 시간 조회 실패: {e}")
		return None

def get_all_held_times():
	"""모든 보유 시간 조회 (dict 형태로 반환)"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT code, held_since FROM held_times')
			return {row['code']: row['held_since'] for row in cursor.fetchall()}
	except Exception as e:
		logger.error(f"전체 보유 시간 조회 실패: {e}")
		return {}

def delete_held_time(code):
	"""보유 시간 삭제 (매도 시)"""
	try:
		with get_db_connection() as conn:
			conn.execute('DELETE FROM held_times WHERE code = ?', (code,))
			conn.commit()
	except Exception as e:
		logger.error(f"보유 시간 삭제 실패: {e}")

def clear_all_held_times():
	"""모든 보유 시간 초기화"""
	try:
		with get_db_connection() as conn:
			conn.execute('DELETE FROM held_times')
			conn.commit()
			logger.info("모든 보유 시간 초기화 완료")
	except Exception as e:
		logger.error(f"보유 시간 초기화 실패: {e}")

# ==================== Settings ====================

def save_setting(key, value):
	"""설정 저장 (settings.json 대체)"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	
	# JSON 직렬화
	if isinstance(value, (dict, list)):
		value_str = json.dumps(value, ensure_ascii=False)
	elif isinstance(value, bool):
		value_str = 'true' if value else 'false'
	else:
		value_str = str(value)
	
	try:
		with get_db_connection() as conn:
			conn.execute('''
				INSERT OR REPLACE INTO settings (key, value, updated_at)
				VALUES (?, ?, ?)
			''', (key, value_str, timestamp))
			conn.commit()
		return True
		
	except Exception as e:
		logger.error(f"설정 저장 실패 ({key}): {e}")

def get_setting(key, default=None):
	"""설정 조회"""
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT value FROM settings WHERE key = ?', (key,))
			row = cursor.fetchone()
			if row:
				value_str = row['value']
				
				# 타입 복원
				val_lower = value_str.strip().lower()
				if val_lower == 'true': return True
				if val_lower == 'false': return False
				
				# JSON 파싱 시도
				try:
					return json.loads(value_str)
				except:
					# 특정 키(인증키, 계좌번호 등)는 숫자 변환을 건너뛰고 문자열로 유지
					string_keys = ['real_app_key', 'real_app_secret', 'paper_app_key', 'paper_app_secret', 
								  'telegram_token', 'telegram_chat_id', 'my_account']
					if key in string_keys:
						return value_str
						
					# 숫자 변환 시도
					try:
						if '.' in value_str:
							return float(value_str)
						return int(value_str)
					except:
						return value_str
			
			return default
	except Exception as e:
		logger.error(f"설정 조회 실패 ({key}): {e}")
		return default

def get_all_settings():
	"""모든 설정 조회 (파일 우선, DB 백업)"""
	settings = {}
	
	# 1. settings.json 파일에서 먼저 조회 (성능을 위해 1회용 조회 후 필요시 주석 처리 가능)
	# 단, 사용자 요청에 따라 DB가 우선이므로 파일이 존재해도 DB값이 있다면 DB를 따르거나, 
	# 마이그레이션이 완료된 후에는 파일을 삭제/이동하여 혼선을 방지해야 함.
	try:
		# DB에서 먼저 조회
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT key, value FROM settings')
			rows = cursor.fetchall()
			if rows:
				for row in rows:
					key = row['key']
					value_str = row['value']
					
					# 타입 복원
					string_keys = ['real_app_key', 'real_app_secret', 'paper_app_key', 'paper_app_secret', 
								  'telegram_token', 'telegram_chat_id', 'my_account']
					
					if value_str == 'true': val = True
					elif value_str == 'false': val = False
					elif key in string_keys: val = value_str
					else:
						try:
							if '.' in value_str: val = float(value_str)
							else: val = int(value_str)
						except:
							val = value_str
					
					settings[key] = val
				return settings
	except Exception as e:
		logger.error(f"모든 설정 조회 실패: {e}")
		return {}

def save_all_settings(settings_dict):
	"""모든 설정 일괄 저장 (DB 통합 트랜잭션 사용)"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	try:
		# [Sync Fix] 키 동기화: 프론트엔드(stop_loss_rate)와 백엔드(sl_rate) 간 불일치 방지
		if 'stop_loss_rate' in settings_dict:
			settings_dict['sl_rate'] = settings_dict['stop_loss_rate']
		elif 'sl_rate' in settings_dict:
			settings_dict['stop_loss_rate'] = settings_dict['sl_rate']

		if not settings_dict:
			return True
			
		with get_db_connection() as conn:
			# [Reliability] BEGIN IMMEDIATE를 사용하여 쓰기 잠금을 즉시 획득 (교착 상태 방지)
			conn.execute("BEGIN IMMEDIATE TRANSACTION")
			for key, value in settings_dict.items():
				# JSON 직렬화
				if isinstance(value, (dict, list)):
					value_str = json.dumps(value, ensure_ascii=False)
				elif isinstance(value, bool):
					value_str = 'true' if value else 'false'
				else:
					value_str = str(value)
				
				conn.execute('''
					INSERT OR REPLACE INTO settings (key, value, updated_at)
					VALUES (?, ?, ?)
				''', (key, value_str, timestamp))
			conn.commit()
			
		logger.info(f"설정 {len(settings_dict)}개 일괄 저장 완료 (트랜잭션)")
		return True
	except Exception as e:
		logger.error(f"일괄 설정 저장 실패: {e}")
		return False

# ==================== Status (Real-time) ====================

# 전역 캐시 변수
_status_cache = {}
_last_status_time = 0

def get_current_status(mode='MOCK'):
	"""
	실시간 상태 조회 (status.json 대체)
	DB에서 직접 계산하여 반환 (Real 모드는 캐시 적용)
	"""
	global _status_cache, _last_status_time
	
	# Real 모드 캐시 적용 (15초 주기로 API 호출)
	if mode == 'REAL':
		now = time.time()
		if _status_cache and (now - _last_status_time < 15):
			# 캐시 반환 시 bot_running 상태만 업데이트
			_status_cache['summary']['bot_running'] = get_bot_running()
			return _status_cache

	try:
		# 설정 로드
		target_stock_count = get_setting('target_stock_count', 5)
		split_buy_cnt = get_setting('split_buy_cnt', 3)
		
		# [Fix] 모든 변수들 초기화 (UnboundLocalError 방지)
		holdings = []
		total_buy = 0
		total_eval = 0
		total_asset = 0
		deposit = 0
		total_pl = 0
		
		with get_db_connection() as conn:
			
			if mode == 'MOCK':
				# 0. 계좌 정보 먼저 조회 (전체 계산을 위해 필수)
				acc_row = conn.execute('SELECT cash FROM mock_account WHERE id=1').fetchone()
				deposit = int(acc_row['cash']) if acc_row else 0
				
				# 보유 주식 총 평가액 먼저 계산
				eval_cursor = conn.execute('SELECT SUM(h.qty * p.current) as total_eval FROM mock_holdings h JOIN mock_prices p ON h.code = p.code WHERE h.qty > 0')
				eval_row = eval_cursor.fetchone()
				total_eval = int(eval_row['total_eval']) if eval_row and eval_row['total_eval'] else 0
				
				total_asset = deposit + total_eval
				
				# [추가] 단계 계산을 위한 총 매입원금(Principal) 선행 계산
				pur_cursor = conn.execute('SELECT SUM(qty * avg_price) as total_pur FROM mock_holdings WHERE qty > 0')
				pur_row = pur_cursor.fetchone()
				total_buy_principal = int(pur_row['total_pur']) if pur_row and pur_row['total_pur'] else 0
				
				# 1. Mock 모드: mock_holdings와 mock_prices에서 세부 종목 조회
				cursor = conn.execute('''
					SELECT 
						h.code, s.name, h.qty, h.avg_price, p.current as current_price
					FROM mock_holdings h
					LEFT JOIN mock_stocks s ON h.code = s.code
					LEFT JOIN mock_prices p ON h.code = p.code
					WHERE h.qty > 0
				''')
				
				for row in cursor.fetchall():
					code = row['code']
					name = row['name'] or code
					qty = int(row['qty'])
					avg_price = float(row['avg_price'])
					cur_price = float(row['current_price']) if row['current_price'] else avg_price
					
					pur_amt = int(avg_price * qty)
					evlt_amt = int(cur_price * qty)
					pl_amt = evlt_amt - pur_amt
					pl_rt = (pl_amt / pur_amt * 100) if pur_amt > 0 else 0
					
					total_buy += pur_amt
					
					# 보유 시간
					held_since = get_held_time(code)
					hold_time = "0분"
					if held_since:
						minutes = int((time.time() - held_since) / 60)
						hold_time = f"{minutes}분"
					
					# [Sync] 1:1:2:4:8 가중치 기반 단계 계산
					st_mode = get_setting('single_stock_strategy', 'WATER').upper()
					s_cnt = int(get_setting('split_buy_cnt', 5))
					
					weights = []
					for i in range(s_cnt):
						if i == 0: weights.append(1)
						else: weights.append(2**(i - 1))
					tw = sum(weights)
					
					cumulative_ratios = []
					curr_s = 0
					for w in weights:
						curr_s += w
						cumulative_ratios.append(curr_s / tw)
					
					# [Step Calc] Transaction Count Method (매수 명령 횟수 = 단계)
					# 마지막 매도 이후 매수 횟수를 세어 단계 결정 (1번=1차, 2번=2차...)
					try:
						cursor_step = conn.execute('''
							SELECT COUNT(*) FROM trades 
							WHERE mode = ? AND code = ? AND type = 'buy'
							AND timestamp > (
								SELECT COALESCE(MAX(timestamp), '2000-01-01') 
								FROM trades 
								WHERE mode = ? AND code = ? AND type = 'sell'
							)
						''', (mode, code, mode, code))
						actual_step = int(cursor_step.fetchone()[0])
						if actual_step < 1:
							actual_step = 1
					except:
						actual_step = 1

					# [CRITICAL Fix] 1주 보유 시 무조건 1단계로 고정
					if qty <= 1:
						actual_step = 1

					display_step = actual_step if actual_step <= s_cnt else s_cnt
					if display_step == 0: display_step = 1
					
					step_str = f"{display_step}차"
					if display_step >= s_cnt: step_str += "(MAX)"
					
					holdings.append({
						'stk_cd': code, 'stk_nm': name, 'qty': qty, 'rmnd_qty': qty,
						'avg_prc': avg_price, 'cur_prc': cur_price,
						'pur_amt': pur_amt, 'evlt_amt': evlt_amt, 'pl_amt': pl_amt,
						'pl_rt': f"{pl_rt:.2f}", 'hold_time': hold_time,
						'watering_step': step_str, 'note': '매집 중'
					})
				
				total_pl = total_eval - total_buy
				
			else:
				# Real 모드: API에서 실시간 데이터 가져오기
				try:
					from kiwoom_adapter import get_account_data
					import datetime
					
					# 계좌 전체 정보 조회 (보유종목 + 요약정보)
					api_holdings, account_summary = get_account_data()
					
					# 계좌 요약 데이터 파싱 (HTS와 일치 유도)
					if account_summary:
						# [Debug] 모든 필드 출력
						logger.info(f"[Debug] account_summary 전체 필드: {account_summary}")
						
						# 1. 예수금 (HTS '예수금' - T일 잔고 우선)
						deposit = int(account_summary.get('dnca_tot_amt', account_summary.get('d2_entra', account_summary.get('entr', 0))))
						
						# 2. 총자산 (HTS '총평가자산' 또는 '예탁자산총액')
						# prsm_dpst_aset_amt: 추정예탁자산총액 (가장 정확한 순자산)
						# tot_evlu_amt: 총평가금액 (이미 매수된 종목 평가액 + 예수금)
						total_asset = int(account_summary.get('prsm_dpst_aset_amt', account_summary.get('tot_evlu_amt', 0)))
						
						# 3. 총매입금액
						total_buy = int(account_summary.get('tot_pur_amt', account_summary.get('tot_pchs_amt', 0)))
						
						# 4. 평가손익 및 평가금액 (종목들)
						# tot_est_amt가 종목들의 총평가금액인 경우가 많음
						total_eval_stocks = int(account_summary.get('tot_est_amt', account_summary.get('aset_evlt_amt', 0)))
						
						# 안전장치: 만약 total_asset이 너무 작게 잡혔으면 (예: 예수금만 잡힘) 보정
						if total_asset < deposit:
							total_asset = deposit + total_eval_stocks
						
						# 5. 실현손익 (당일 실현손익 우선)
						api_total_pl = int(account_summary.get('tdy_lspft_amt', account_summary.get('tot_pl', 0)))
						
						if api_total_pl != 0:
							total_pl = api_total_pl
						else:
							# API가 0이면 trades 테이블에서 오늘 완료된 매매 손익 합산
							today = datetime.date.today().strftime('%Y-%m-%d')
							cursor = conn.execute('''
								SELECT SUM(CASE WHEN type='sell' THEN amt * (profit_rate / 100.0) ELSE 0 END) as realized_profit
								FROM trades
								WHERE mode = ? AND type='sell' AND timestamp LIKE ?
							''', (mode, f'{today}%'))
							row = cursor.fetchone()
							total_pl = int(row['realized_profit']) if row and row['realized_profit'] else 0
							
						logger.info(f"[Real 모드 Summary] 총자산: {total_asset:,}, 예수금: {deposit:,}, 총매입: {total_buy:,}, 실현손익: {total_pl:,}")
					else:
						deposit = total_asset = total_buy = total_pl = 0

					# [추가] 종목당 할당액 계산
					# 유저 요청: 손익률/평가금에 따라 단계가 변하지 않도록 원금 기준(예수금+총내입금) 사용
					principal_basis = deposit + total_buy
					capital_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0
					target_stock_count_val = float(get_setting('target_stock_count', 5))
					alloc_per_stock = (principal_basis * capital_ratio) / target_stock_count_val if target_stock_count_val > 0 else 1
					split_buy_cnt_val = int(get_setting('split_buy_cnt', 5))

					# 보유종목 상세 정보 구성
					if api_holdings:
						# trades 테이블에서 평균가 미리 계산 (API 보정용)
						avg_prices_from_db = {}
						cursor = conn.execute('SELECT code, SUM(amt)/SUM(qty) FROM trades WHERE mode = ? AND type = "buy" GROUP BY code', (mode,))
						for row in cursor.fetchall():
							if row[0] and row[1]:
								avg_prices_from_db[row[0]] = float(row[1])

						for stock in api_holdings:
							code = stock.get('stk_cd', '').replace('A', '')
							name = stock.get('stk_nm', code)
							qty = int(stock.get('rmnd_qty', 0))
							if qty <= 0: continue
							
							api_avg = float(stock.get('avg_prc', 0))
							avg_price = api_avg if api_avg > 0 else avg_prices_from_db.get(code, 0)
							cur_price = float(stock.get('cur_prc', avg_price))
							
							pur_amt = int(avg_price * qty)
							evlt_amt = int(cur_price * qty)
							pl_amt = evlt_amt - pur_amt
							pl_rt = f"{(pl_amt / pur_amt * 100):.2f}" if pur_amt > 0 else "0.00"
							
							# [Fix] watering_step 및 hold_time 로직 보강
							held_since = get_held_time(code)
							hold_time = "조회중"
							if held_since:
								minutes = int((time.time() - held_since) / 60)
								hold_time = f"{minutes}분"
							
							# [Step Calc] Transaction Count Method (매수 명령 횟수 = 단계)
							# 마지막 매도 이후 매수 횟수를 세어 단계 결정 (1번=1차, 2번=2차...)
							try:
								cursor = conn.execute('''
									SELECT COUNT(*) FROM trades 
									WHERE mode = ? AND code = ? AND type = 'buy'
									AND timestamp > (
										SELECT COALESCE(MAX(timestamp), '2000-01-01') 
										FROM trades 
										WHERE mode = ? AND code = ? AND type = 'sell'
									)
								''', (mode, code, mode, code))
								step_idx = int(cursor.fetchone()[0])
								if step_idx < 1:
									step_idx = 1
								
								display_step = step_idx if step_idx <= split_buy_cnt_val else split_buy_cnt_val
								
								# [CRITICAL Fix] 1주 보유 시 무조건 1단계로 고정
								if qty <= 1:
									display_step = 1
									
								step_str = f"{display_step}차"
								if display_step >= split_buy_cnt_val: 
									step_str += "(MAX)"
							except:
								step_str = "보유중"



							holdings.append({
								'stk_cd': code, 'stk_nm': name, 'qty': qty, 'rmnd_qty': qty,
								'avg_prc': avg_price, 'cur_prc': cur_price,
								'pur_amt': pur_amt, 'evlt_amt': evlt_amt, 'pl_amt': pl_amt,
								'pl_rt': pl_rt, 'hold_time': hold_time,
								'watering_step': step_str, 'note': '매집 중'
							})
							
							# 만약 total_buy가 0이면 여기서 누적 (보조용)
							if total_buy == 0:
								total_buy += pur_amt
								
				except Exception as e:
					logger.error(f"Real 모드 에러: {e}")
					import traceback
					traceback.print_exc()


			# [Fix] 수익률 계산 로직 (공통)
			# HTS와 일치시키기 위해 '실현손익'이 아닌 '평가손익' 기준
			current_eval_profit = 0
			if mode == 'MOCK':
				current_eval_profit = total_pl
			else:
				# Real 모드: 총평가금 - 총매입금
				try:
					current_eval_profit = total_eval_stocks - total_buy
				except:
					current_eval_profit = 0

			total_yield = (current_eval_profit / total_buy * 100) if total_buy > 0 else 0
			
			# 봇 실행 상태 조회
			bot_running = get_bot_running()
			
			result = {
				'summary': {
					'total_asset': total_asset,
					'total_buy': total_buy,
					'deposit': deposit,
					'total_pl': total_pl,
					'total_yield': total_yield,
					'bot_running': bot_running,
					'api_mode': mode,
					'is_paper': mode == 'MOCK'
				},
				'holdings': holdings
			}
			# [Sensitive Update] 캐시 사용 안 함 (무조건 실시간)
			return result
			
	except Exception as e:
		logger.error(f"상태 조회 실패: {e}")
		return {
			'error': True,
			'message': str(e),
			'summary': {
				'total_asset': 0,
				'total_buy': 0,
				'deposit': 0,
				'total_pl': 0,
				'total_yield': 0,
				'bot_running': False,
				'api_mode': mode,
				'is_paper': mode == 'MOCK'
			},
			'holdings': []
		}


# ==================== Migration ====================

def migrate_json_files_to_db():
	"""기존 JSON 파일들을 DB로 마이그레이션"""
	base_dir = os.path.dirname(os.path.abspath(__file__))
	
	# 1. held_times.json 마이그레이션
	held_times_file = os.path.join(base_dir, 'held_times.json')
	if os.path.exists(held_times_file):
		try:
			with open(held_times_file, 'r', encoding='utf-8') as f:
				held_times = json.load(f)
			
			for code, held_since in held_times.items():
				save_held_time(code, held_since)
			
			# 백업
			os.rename(held_times_file, held_times_file + '.backup')
			logger.info(f"✅ held_times.json 마이그레이션 완료: {len(held_times)}개")
		except Exception as e:
			logger.error(f"held_times.json 마이그레이션 실패: {e}")
	
	# 2. settings.json 마이그레이션
	settings_file = os.path.join(base_dir, 'settings.json')
	if os.path.exists(settings_file):
		try:
			with open(settings_file, 'r', encoding='utf-8') as f:
				settings = json.load(f)
			
			save_all_settings(settings)
			
			# 강력 마이그레이션: 파일 이름을 완전히 변경하여 접근 차단
			os.rename(settings_file, settings_file + '.migrated_to_db')
			logger.info(f"✅ settings.json 마이그레이션 및 비활성화 완료")
		except Exception as e:
			logger.error(f"settings.json 마이그레이션 실패: {e}")
	
	# 3. daily_asset 마이그레이션
	try:
		from database_daily_asset import migrate_daily_asset_json
		migrate_daily_asset_json()
	except Exception as e:
		logger.error(f"daily_asset 마이그레이션 실패: {e}")
	
	logger.info("🎉 모든 JSON 파일 마이그레이션 완료!")
# ==================== System Status & Web Commands ====================

def save_system_status(status_data):
	"""실시간 봇 상태 저장 (모드별 분리 저장)"""
	timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	try:
		# 데이터 내부의 api_mode 확인 (summary 내부에 있을 수 있음)
		mode = status_data.get('api_mode')
		if not mode and 'summary' in status_data:
			mode = status_data['summary'].get('api_mode')
		
		if not mode: mode = 'REAL'
		mode = mode.upper()
		
		status_json = json.dumps(status_data, ensure_ascii=False)
		
		with get_db_connection() as conn:
			conn.execute('''
				INSERT OR REPLACE INTO system_status (api_mode, status_json, updated_at)
				VALUES (?, ?, ?)
			''', (mode, status_json, timestamp))
			conn.commit()
		return True
	except Exception as e:
		logger.error(f"시스템 상태 DB 저장 실패: {e}")
		return False

def get_system_status(mode=None):
	"""실시간 봇 상태 조회 (모드 필터링)"""
	if mode is None:
		try:
			from kiwoom_adapter import get_current_api_mode
			mode = get_current_api_mode().upper()
		except:
			mode = "REAL"
	else:
		mode = str(mode).upper()
		
	try:
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT status_json FROM system_status WHERE UPPER(api_mode) = ?', (mode,))
			row = cursor.fetchone()
			if row:
				return json.loads(row['status_json'])
		return None
	except Exception as e:
		logger.error(f"시스템 상태 DB 조회 실패 (Mode: {mode}): {e}")
		return None

def set_bot_running(is_running):
	"""봇 실행 상태 설정"""
	try:
		save_setting('bot_running', is_running)
		logger.info(f"봇 실행 상태 업데이트: {is_running}")
		return True
	except Exception as e:
		logger.error(f"봇 실행 상태 업데이트 실패: {e}")
		return False

def get_bot_running():
	"""봇 실행 상태 조회"""
	try:
		return get_setting('bot_running', False)
	except Exception as e:
		logger.error(f"봇 실행 상태 조회 실패: {e}")
		return False

def add_web_command(command, params=None):
	"""웹 명령 추가 (web_command.json 대체)"""
	timestamp = datetime.now().isoformat() if hasattr(datetime, 'now') else datetime.datetime.now().isoformat()
	params_json = json.dumps(params, ensure_ascii=False) if params else None
	try:
		with get_db_connection() as conn:
			conn.execute('''
				INSERT INTO web_commands (command, params, status, timestamp)
				VALUES (?, ?, 'pending', ?)
			''', (command, params_json, timestamp))
			conn.commit()
		return True
	except Exception as e:
		logger.error(f"웹 명령 DB 저장 실패: {e}")
		return False

def get_pending_web_command():
	"""대기 중인 최신 명령 조회"""
	try:
		with get_db_connection() as conn:
			# 가장 최근의 pending 명령 하나 가져옴
			cursor = conn.execute('''
				SELECT id, command, params, timestamp 
				FROM web_commands 
				WHERE status = 'pending' 
				ORDER BY id DESC LIMIT 1
			''')
			row = cursor.fetchone()
			if row:
				return {
					"id": row['id'],
					"command": row['command'],
					"params": json.loads(row['params']) if row['params'] else None,
					"timestamp": row['timestamp']
				}
		return None
	except Exception as e:
		logger.error(f"대기 명령 DB 조회 실패: {e}")
		return None

def mark_web_command_completed(command_id):
	"""명령 처리 완료 표시"""
	try:
		with get_db_connection() as conn:
			conn.execute('UPDATE web_commands SET status = "completed" WHERE id = ?', (command_id,))
			conn.commit()
		return True
	except Exception as e:
		logger.error(f"명령 완료 표시 실패: {e}")
		return False

def clear_old_web_commands(days=1):
	"""오래된 명령 기록 삭제"""
	cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
	try:
		with get_db_connection() as conn:
			conn.execute('DELETE FROM web_commands WHERE timestamp < ?', (cutoff,))
			conn.commit()
		return True
	except Exception as e:
		logger.error(f"오래된 명령 삭제 실패: {e}")
		return False
