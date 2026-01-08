import json
import os
import asyncio
import datetime
import time
from rt_search import RealTimeSearch
from tel_send import tel_send
from check_n_sell import chk_n_sell
from check_n_buy import reset_accumulation
# [Mock Server Integration] Use kiwoom_adapter for automatic Real/Mock API switching
from kiwoom_adapter import fn_kt00004, get_total_eval_amt
from kiwoom_adapter import fn_kt00001 as get_balance
from kiwoom_adapter import fn_au10001
from market_hour import MarketHour
from get_seq import get_condition_list
from logger import logger
from settings_validator import SettingsValidator
from sell_all_stocks import sell_all_stocks
from get_setting import get_setting, set_setting
from trading_log_parser import get_trading_logs
from database_trading_log import get_trading_logs_from_db

class ChatCommand:
	def __init__(self):
		self.rt_search = RealTimeSearch(on_connection_closed=self._on_connection_closed)
		self.script_dir = os.path.dirname(os.path.abspath(__file__))
		# [Mode Check] 파일 분리 (Mock/Real)
		self.mode_suffix = "_mock"
		if not get_setting('use_mock_server', True):
			self.mode_suffix = "_real"
		
		self.daily_asset_path = os.path.join(self.script_dir, f'daily_asset{self.mode_suffix}.json') # 일일 자산 저장 경로
		self.check_n_sell_task = None  # check_n_sell 백그라운드 태스크
		self.token = None  # 현재 사용 중인 토큰
		self.initial_asset = 500000000 # 금일 시초 자산 (5억 고정)
		self.held_since = {} # [Time-Cut] 보유 시각 (MainApp에서 주입받음)
		self.liquidation_done = False # [Liquidation] 자동 청산 중첩 방지
	
	def get_token(self, force=False):
		"""새로운 토큰을 발급받습니다. (중복 발급 방지 + DB 캐싱 + 만료 추적)"""
		try:
			import time
			# [NEW] 모드별 토큰 DB 필드 분리
			trading_mode = get_setting('trading_mode', 'MOCK').upper()
			token_key = f'api_token_{trading_mode}'
			token_time_key = f'api_token_time_{trading_mode}'
			
			logger.info(f"🔑 토큰 확인 중... (모드: {trading_mode})")
			
			# DB에서 저장된 토큰 읽기
			if not force:
				try:
					saved_token = get_setting(token_key)
					
					# 토큰 발급 시간 확인
					token_age_hours = 999
					saved_time = get_setting(token_time_key)
					if saved_time:
						token_time = float(saved_time)
						token_age_hours = (time.time() - token_time) / 3600
					
					# 토큰이 24시간 미만이면 재사용
					if saved_token and token_age_hours < 24:
						self.token = saved_token
						logger.info(f"✅ 저장된 토큰 재사용 (모드: {trading_mode}, 발급 후 {token_age_hours:.1f}시간 경과)")
						return saved_token
					else:
						if saved_token:
							logger.info(f"⏰ 저장된 토큰 만료됨 ({token_age_hours:.1f}시간 경과)")
				except Exception as e:
					logger.warning(f"저장된 토큰 읽기 실패: {e}")
			
			# 이미 메모리에 토큰이 있고 강제 갱신이 아니면 재사용
			if self.token and not force:
				logger.info(f"기존 토큰 재사용: {self.token[:10]}...")
				return self.token

			# 새 토큰 발급 (하루 1회 제한 확인 - 5회 제한 보호용)
			try:
				last_issue_time_val = get_setting(token_time_key)
				if last_issue_time_val:
					last_issue_time = float(last_issue_time_val)
					hours_since_last = (time.time() - last_issue_time) / 3600
					
					# 마지막 발급 후 1시간 미만이면 발급 안 함 (강제 갱신은 허용)
					if hours_since_last < 1 and not force:
						logger.warning(f"⚠️ 토큰 발급 제한: 마지막 발급 후 {hours_since_last:.1f}시간 경과 (1시간 후 재시도 가능)")
						return None
			except:
				pass
			
			logger.info("🔑 새 토큰 발급 시도...")
			token = fn_au10001()
			if token:
				self.token = token
				# 토큰과 발급 시간을 DB에 저장
				try:
					from database_helpers import save_setting
					save_setting(token_key, token)
					save_setting(token_time_key, str(time.time()))
					logger.info(f"✅ 새로운 토큰 발급 완료 및 DB 저장: {token[:10]}...")
				except Exception as e:
					logger.warning(f"토큰 DB 저장 실패: {e}")
				return token
			else:
				# Mock 모드에서는 토큰 오류 표시 안 함
				use_mock = get_setting('use_mock_server', True)
				if not use_mock:
					logger.warning("⚠️ 토큰 발급 실패 - API 키/Secret 또는 5회 제한을 확인하세요")
				return None
		except Exception as e:
			logger.error(f"토큰 발급 중 오류: {e}", exc_info=True)
			return None
	
	async def _on_connection_closed(self):
		"""WebSocket 연결이 종료되었을 때 호출되는 콜백 함수"""
		try:
			# Event loop가 닫힌 경우 처리 중단
			logger.warning("WebSocket 연결이 종료되어 자동으로 stop을 실행합니다.")
			
			# [Fix] 의도적으로 종료된 경우(stop 명령어 등)는 재시작하지 않음
			if not self.rt_search.keep_running:
				logger.info("의도적인 종료로 판단되어 자동 재시작을 스킵합니다.")
				return

			tel_send("⚠️ 서버 연결이 끊어져 자동으로 서비스를 재시작합니다.")
			await self.stop(set_auto_start_false=False)  # auto_start는 그대로 유지

			logger.info("1초 후 서비스를 재시작합니다.")
			await asyncio.sleep(1)
			await self.start()
		except RuntimeError as e:
			if "no running event loop" in str(e) or "Event loop is closed" in str(e):
				logger.warning(f"Event loop 종료로 인해 재시작을 취소합니다: {e}")
			else:
				logger.error(f"연결 종료 콜백 실행 중 오류: {e}", exc_info=True)
		except Exception as e:
			logger.error(f"연결 종료 콜백 실행 중 오류: {e}", exc_info=True)
			try:
				tel_send(f"❌ 연결 종료 처리 중 오류가 발생했습니다: {e}")
			except:
				pass  # 텔레그램 전송도 실패할 수 있음
	
	def update_setting(self, key, value):
		"""DB 설정을 업데이트합니다."""
		try:
			# 설정 값 검증
			is_valid, error_msg = SettingsValidator.validate_setting(key, value)
			if not is_valid:
				logger.error(f"설정 값 검증 실패: {error_msg}")
				return False
			
			# DB에 저장
			if set_setting(key, value):
				logger.info(f"설정 업데이트 성공: {key} = {value}")
				return True
			else:
				return False
		except Exception as e:
			logger.error(f"설정 업데이트 실패: {e}", exc_info=True)
			return False
	
	async def start(self):
		"""start 명령어를 처리합니다."""
		if self.rt_search.connected:
			logger.info("이미 실시간 검색이 실행 중입니다. 중복 시작을 건너뜁니다.")
			return True
			
		try:
			# 기존 check_n_sell 태스크가 실행 중이면 정지
			if self.check_n_sell_task and not self.check_n_sell_task.done():
				print("기존 check_n_sell 태스크를 정지합니다")
				self.check_n_sell_task.cancel()
				try:
					await self.check_n_sell_task
				except asyncio.CancelledError:
					pass
			
			# 새로운 토큰 발급
			token = self.get_token()
			if not token:
				tel_send("❌ 토큰 발급에 실패했습니다")
				return False
			
			# auto_start를 true로 설정
			self.update_setting('auto_start', True)
			from database_helpers import set_bot_running
			set_bot_running(True) # 봇이 일단 의지를 가졌으므로 실행 중으로 표시
			
			# [Fix] Mock 모드라면 장 시간과 무관하게 통과
			from market_hour import MarketHour
			is_mock_mode = MarketHour._is_mock_mode()
			
			if not MarketHour.is_market_open_time() and not is_mock_mode:
				tel_send(f"⏰ 장이 열리지 않았습니다. 장 시작 시간({MarketHour.MARKET_START_HOUR:02d}:{MarketHour.MARKET_START_MINUTE:02d})에 자동으로 시작됩니다.")
				return True
			elif is_mock_mode:
				logger.info("🎮 Mock 모드 - 장 시간과 무관하게 즉시 시작합니다.")
			
			# WebSocket 연결 재시도 로직
			max_retries = 5  # 최대 재시도 횟수
			retry_delay = 2  # 초기 재시도 간격 (초)
			
			for attempt in range(max_retries):
				try:
					# rt_search의 start 실행 (토큰 전달)
					
					# [수정] 봇을 (재)시작할 때, 이전 실행에서 매도하여 금지된 목록을 초기화할지 선택
					# 사용자가 'start'를 눌렀다는 건 새로운 마음으로 시작하겠다는 뜻이 강하므로 리셋
					# 단, 장중에 껐다 켰을 때 중복 매수 위험이 있으나, '보유 종목 동기화' 로직이 막아줌.
					self.rt_search.purchased_stocks.clear()
					logger.info("봇 시작 시 매수 금지 목록을 초기화했습니다.")

					success = await self.rt_search.start(token)
					
					if success:
						# check_n_sell 백그라운드 태스크 시작 -> MainApp 루프로 통합 (제거)
						# self.check_n_sell_task = asyncio.create_task(self._check_n_sell_loop())
						# 봇 실행 상태 DB에 저장
						from database_helpers import set_bot_running
						set_bot_running(True)
						
						tel_send("✅ 실시간 검색과 자동 매도 체크가 시작되었습니다. (매수 금지 목록 초기화됨)")
						return True
					else:
						# 연결 실패 시 재시도
						if attempt < max_retries - 1:  # 마지막 시도가 아닌 경우
							print(f"WebSocket 연결 실패, {retry_delay}초 후 재시도합니다... ({attempt + 1}/{max_retries})")
							tel_send(f"⚠️ WebSocket 연결 실패, {retry_delay}초 후 재시도합니다... ({attempt + 1}/{max_retries})")
							
							# 지수 백오프: 재시도 간격을 점진적으로 증가
							await asyncio.sleep(retry_delay)
							retry_delay = min(retry_delay * 1.5, 10)  # 최대 10초까지
							
							# 토큰 갱신 (연결 실패 시 토큰이 만료되었을 가능성)
							new_token = self.get_token()
							if new_token:
								token = new_token
						else:
							# 마지막 시도도 실패한 경우
							print(f"WebSocket 연결이 {max_retries}번 연속 실패했습니다.")
							tel_send(f"❌ WebSocket 연결이 {max_retries}번 연속 실패했습니다. 나중에 다시 'start' 명령어를 입력해주세요.")
							return False
							
				except Exception as e:
					if attempt < max_retries - 1:  # 마지막 시도가 아닌 경우
						print(f"WebSocket 연결 중 오류 발생, {retry_delay}초 후 재시도합니다... ({attempt + 1}/{max_retries}): {e}")
						tel_send(f"⚠️ WebSocket 연결 중 오류 발생, {retry_delay}초 후 재시도합니다... ({attempt + 1}/{max_retries})")
						
						await asyncio.sleep(retry_delay)
						retry_delay = min(retry_delay * 1.5, 10)  # 최대 10초까지
						
						# 토큰 갱신
						new_token = self.get_token()
						if new_token:
							token = new_token
					else:
						# 마지막 시도도 실패한 경우
						print(f"WebSocket 연결이 {max_retries}번 연속 실패했습니다: {e}")
						tel_send(f"❌ WebSocket 연결이 {max_retries}번 연속 실패했습니다: {e}")
						return False
			
			return False
				
		except Exception as e:
			tel_send(f"❌ start 명령어 실행 중 오류: {e}\n계속 재시작이 되지 않으면 'start' 명령어를 다시 입력해주세요.")
			return False
	
	async def stop(self, set_auto_start_false=True):
		"""stop 명령어를 처리합니다."""
		try:
			# stop 명령 실행 시 auto_start 설정을 끄도록 처리 (루프 재시작 방지)
			# [User Request] 프로그램을 시작하면 자동시작이 되어야 하므로, stop 시에도 auto_start를 끄지 않음
			if set_auto_start_false:
				try:
					# set_setting('auto_start', False) # 자동 시작 해제 방지
					logger.info("stop 명령이 실행되었지만, auto_start 설정은 유지합니다.")
				except Exception as e:
					logger.error(f"auto_start 설정 저장 실패: {e}")
			
			# check_n_sell 백그라운드 태스크 정지
			if self.check_n_sell_task and not self.check_n_sell_task.done():
				logger.info("check_n_sell 백그라운드 태스크를 정지합니다")
				self.check_n_sell_task.cancel()
				try:
					await self.check_n_sell_task
				except asyncio.CancelledError:
					pass
			
			# rt_search의 stop 실행
			success = await self.rt_search.stop()
			
			if success:
				# 봇 실행 상태 DB에 저장
				from database_helpers import set_bot_running
				set_bot_running(False)
				
				tel_send("✅ 실시간 검색과 자동 매도 체크가 중지되었습니다")
				return True
			else:
				tel_send("❌ 실시간 검색 중지에 실패했습니다")
				return False
				
		except Exception as e:
			logger.error(f"❌ stop 명령어 실행 중 오류: {e}")
			return False
	
	async def report(self, send_telegram=True):
		"""report 명령어를 처리합니다 - acc_val 실행 결과를 텔레그램으로 발송"""
		# [Web Report] 매매 내역 업데이트 (trading_log.json & sell_log.json)
		# [Server Sync] 키움 서버에서 오늘의 체결 내역 가져오기
		try:
			from kiwoom_adapter import fn_opw00007
			server_trades = fn_opw00007(self.token)
			
			# 서버 데이터를 buys/sells로 분류
			logs = {"buys": [], "sells": []}
			for trade in server_trades:
				trade_type = trade.get('type', '').upper()
				if trade_type in ['BUY', '매수']:
					logs['buys'].append(trade)
				elif trade_type in ['SELL', '매도']:
					logs['sells'].append(trade)
			
			logger.info(f"[Server Sync] 키움 서버에서 체결내역 조회 완료 (Buy: {len(logs['buys'])}, Sell: {len(logs['sells'])})")
		except Exception as e:
			logger.warning(f"서버 체결내역 조회 실패, 로컬 로그 사용: {e}")
			logs = get_trading_logs()
		
		# DB에 체결 내역 동기화 (필요 시 로직 추가 가능, 현재는 파일 저장만 제거)
		# 봇은 이미 실시간으로 DB에 기록하므로 일치할 것임.
		logger.info(f"체결내역 동기화 프로세스 (DB 연동 시 파일 저장 스킵)")

		try:
			# 토큰이 없으면 새로 발급
			if not self.token:
				token = self.get_token()
				if not token:
					if send_telegram: tel_send("❌ 토큰 발급에 실패했습니다")
					return False
			
			# acc_val 실행 (타임아웃 10초)
			try:
				account_data = await asyncio.wait_for(
					asyncio.get_event_loop().run_in_executor(None, fn_kt00004, False, 'N', '', self.token),
					timeout=10.0
				)
			except asyncio.TimeoutError:
				if send_telegram: tel_send("⏰ 서버로부터 응답이 늦어지고 있습니다. 나중에 다시 시도해주세요.")
				return False
			
			# 2. 자산 현황 조회 (현금, 주식평가) - 추가된 부분
			try:
				# cash_balance: 주문가능금액, deposit_amt: 예수금
				cash_balance, _, deposit_amt = await asyncio.get_event_loop().run_in_executor(
					None, get_balance, 'N', '', self.token
				)
				stock_eval = await asyncio.get_event_loop().run_in_executor(
					None, get_total_eval_amt, self.token
				)
				# 순자산 = 예수금 + 주식평가금액
				total_net_asset = deposit_amt + stock_eval
				
				# (참고용) 레버리지 포함 자산 = 주문가능금액 + 주식평가금액
				buying_power_asset = cash_balance + stock_eval
				
			except Exception as e:
				logger.error(f"자산 조회 중 오류: {e}")
				cash_balance = 0
				deposit_amt = 0
				stock_eval = 0
				total_net_asset = 0
			
			# 데이터 정리 및 포맷팅
			message = "📊 [자산 현황 보고서]\n"
			message += f"💰 총 순자산: {total_net_asset:,.0f}원\n"
			message += f"💵 예수금: {deposit_amt:,.0f}원\n"
			message += f"💳 주문가능금액: {cash_balance:,.0f}원\n"
			message += f"📈 주식평가금액: {stock_eval:,.0f}원\n"
			message += "-" * 20 + "\n\n"
			
			if not account_data:
				message += "ℹ️ 현재 보유 중인 종목이 없습니다.\n"
				if send_telegram: tel_send(message)
				# 여기서도 리턴하면 안되고 아래 매도 로그 업데이트로 넘어가야 함
				# return True (제거)
			
			else:
				message += "📦 [보유 종목 상세]\n\n"
				
				total_profit_loss = 0
				total_pl_amt = 0
				
				for stock in account_data:
					stock_code = stock.get('stk_cd', 'N/A')
					stock_name = stock.get('stk_nm', 'N/A')
					
					# 안전한 숫자 변환
					try:
						profit_loss_rate = float(str(stock.get('pl_rt', 0)).replace(',', ''))
					except: profit_loss_rate = 0.0
					
					try:
						pl_amt = int(float(str(stock.get('pl_amt', 0)).replace(',', '')))
					except: pl_amt = 0
					
					try:
						remaining_qty = int(float(str(stock.get('rmnd_qty', 0)).replace(',', '')))
					except: remaining_qty = 0
					
					# 수익률에 따른 이모지 설정
					if profit_loss_rate > 0:
						emoji = "🔴"
					elif profit_loss_rate < 0:
						emoji = "🔵"
					else:
						emoji = "➡️"
					
					message += f"{emoji} [{stock_name}] ({stock_code})\n"
					message += f"   수익률: {profit_loss_rate:+.2f}%\n"
					message += f"   평가손익: {pl_amt:,.0f}원\n"
					message += f"   보유수량: {remaining_qty:,}주\n\n"
					
					total_profit_loss += profit_loss_rate
					total_pl_amt += pl_amt
				
				# 전체 요약
				avg_profit_loss = total_profit_loss / len(account_data) if account_data else 0
				message += f"📋 [전체 요약]\n"
				message += f"   총 보유종목: {len(account_data)}개\n"
				message += f"   평균 수익률: {avg_profit_loss:+.2f}%\n"
				message += f"   총 평가손익: {total_pl_amt:,.0f}원\n"
				
				if send_telegram: tel_send(message)



			return True
			
		except Exception as e:
			tel_send(f"❌ report 명령어 실행 중 오류: {e}")
			return False
	
	async def tpr(self, number):
		"""tpr 명령어를 처리합니다 - take_profit_rate 수정"""
		try:
			rate = float(number)
			if self.update_setting('take_profit_rate', rate):
				tel_send(f"✅ 익절 기준이 {rate}%로 설정되었습니다")
				return True
			else:
				tel_send("❌ 익절 기준 설정에 실패했습니다")
				return False
		except ValueError:
			tel_send("❌ 잘못된 숫자 형식입니다. 예: tpr 5")
			return False
		except Exception as e:
			tel_send(f"❌ tpr 명령어 실행 중 오류: {e}")
			return False
	
	async def slr(self, number):
		"""slr 명령어를 처리합니다 - stop_loss_rate 수정"""
		try:
			rate = float(number)
			if rate > 0:
				rate = -rate
			if self.update_setting('stop_loss_rate', rate):
				tel_send(f"✅ 손절 기준이 {rate}%로 설정되었습니다")
				return True
			else:
				tel_send("❌ 손절 기준 설정에 실패했습니다")
				return False
		except ValueError:
			tel_send("❌ 잘못된 숫자 형식입니다. 예: slr -10")
			return False
		except Exception as e:
			tel_send(f"❌ slr 명령어 실행 중 오류: {e}")
			return False
	
	async def brt(self, number):
		"""brt 명령어를 처리합니다 - buy_ratio 수정"""
		try:
			ratio = float(number)
			if self.update_setting('buy_ratio', ratio):
				tel_send(f"✅ 매수 비용 비율이 {ratio}%로 설정되었습니다")
				return True
			else:
				tel_send("❌ 매수 비용 비율 설정에 실패했습니다")
				return False
		except ValueError:
			tel_send("❌ 잘못된 숫자 형식입니다. 예: brt 3")
			return False
		except Exception as e:
			tel_send(f"❌ brt 명령어 실행 중 오류: {e}")
			return False
	
	async def condition(self, number=None):
		"""condition 명령어를 처리합니다 - 조건식 목록 조회 또는 search_seq 설정"""
		try:
			# 먼저 stop 실행
			tel_send("🔄 condition 명령어 실행을 위해 서비스를 중지합니다...")
			await self.stop(set_auto_start_false=False)  # auto_start는 그대로 유지
			
			# 숫자가 제공된 경우 search_seq 설정
			if number is not None:
				try:
					seq_number = str(number)
					if self.update_setting('search_seq', seq_number):
						tel_send(f"✅ 검색 조건식이 {seq_number}번으로 설정되었습니다")
						
						# 장 시간일 경우 자동으로 start 실행
						if MarketHour.is_market_open_time():
							tel_send("🔄 장 시간이므로 자동으로 재시작합니다...")
							
							# 잠시 대기
							await asyncio.sleep(2)
							
							# 새로운 설정으로 시작
							success = await self.start()
							if success:
								tel_send("✅ 새로운 조건식으로 재시작되었습니다")
							else:
								tel_send("❌ 재시작에 실패했습니다")
						else:
							tel_send(f"⏰ 장이 열리지 않았습니다. 장 시작 시간({MarketHour.MARKET_START_HOUR:02d}:{MarketHour.MARKET_START_MINUTE:02d})에 자동으로 시작됩니다.")
						
						return True
					else:
						tel_send("❌ 검색 조건식 설정에 실패했습니다")
						return False
				except ValueError:
					tel_send("❌ 잘못된 숫자 형식입니다. 예: condition 0")
					return False
			
			# 숫자가 제공되지 않은 경우 조건식 목록 조회
			# 조건식 목록 가져오기 (타임아웃 10초로 단축)
			try:
				condition_data = await asyncio.wait_for(
					get_condition_list(self.token),
					timeout=10.0
				)
			except asyncio.TimeoutError:
				tel_send("⏰ 조건식 목록 조회가 시간 초과되었습니다. 나중에 다시 시도해주세요.")
				return False
			
			if not condition_data:
				tel_send("📋 조건식 목록이 없습니다.")
				return False
			
			# 조건식 목록 포맷팅
			message = "📋 [조건식 목록]\n\n"
			
			for condition in condition_data:
				condition_id = condition[0] if len(condition) > 0 else 'N/A'
				condition_name = condition[1] if len(condition) > 1 else 'N/A'
				message += f"• {condition_id}: {condition_name}\n"
			
			message += "\n💡 사용법: condition {번호} (예: condition 0)"
			tel_send(message)
			return True
			
		except Exception as e:
			tel_send(f"❌ condition 명령어 실행 중 오류: {e}")
			return False

	async def help(self):
		"""help 명령어를 처리합니다 - 명령어 설명 및 사용법 가이드"""
		try:
			help_message = """🤖 [키움 REST API 봇 명령어 가이드]

			[기본 명령어]
			• start - 실시간 검색과 자동 매도 체크 시작
			• stop - 실시간 검색과 자동 매도 체크 중지
			• report 또는 r - 계좌평가현황 보고서 발송
			• condition - 조건식 목록 조회
			• condition {번호} - 검색 조건식 변경 (예: condition 0)

			[설정 명령어]
			• goal {금액} - 목표 수익금 설정 (예: goal 700000)
			• limit {숫자} - 일일 손실 한도 설정 (예: limit -3)
			• cnt {숫자} - 목표 종목 수 설정 (예: cnt 5)
			• cap {숫자} - 투자 비중 설정 (예: cap 70)
			• ssr {숫자} - 추가매수 간격 설정 (예: ssr 4)
			• tpr {숫자} - 익절 기준 설정 (예: tpr 5)
			• slr {숫자} - 손절 기준 설정 (양수 입력 시 음수로 변환)
			• mwp {0.0~1.0} - 수학 엔진 최소 승률 (예: mwp 0.6)
			• msc {숫자} - 수학 엔진 최소 표본 (예: msc 10)
			
			• factor (또는 f) - 현재 주요 팩터 설정값 조회
			• /set {키} {값} - 상세 설정 변경
			
			• status - 매수 금지 종목 상태 확인
			• reset - 매수 금지 목록 초기화
			• sellall (또는 sa) - 보유 전 종목 일괄 매도
			
			 모든 설정은 즉시 반영됩니다. 자세한 키 목록은 factor 명령어로 확인하세요."""
			
			tel_send(help_message)
			return True
			
		except Exception as e:
			tel_send(f"❌ help 명령어 실행 중 오류: {e}")
			return False

	async def factor(self):
		"""현재 주요 팩터 설정값을 조회합니다."""
		try:
			from settings_validator import SettingsValidator
			keys = [
				'target_stock_count', 'trading_capital_ratio', 'split_buy_cnt',
				'take_profit_rate', 'stop_loss_rate', 'target_profit_amt', 
				'global_loss_rate', 'math_min_win_rate', 'math_min_sample_count',
				'use_rsi_filter', 'rsi_limit'
			]
			
			msg = "⚙️ [현재 주요 팩터 설정]\n\n"
			for key in keys:
				val = get_setting(key, "N/A")
				desc = SettingsValidator.VALIDATION_RULES.get(key, {}).get('description', key)
				msg += f"• {desc} ({key}): {val}\n"
			
			msg += "\n💡 변경법: /set {키} {값}\n예: /set math_min_win_rate 0.6"
			tel_send(msg)
			return True
		except Exception as e:
			tel_send(f"❌ factor 조회 오류: {e}")
			return False

	async def status(self):
		"""현재 매수 금지 목록(purchased_stocks)을 확인합니다."""
		try:
			stocks = self.rt_search.purchased_stocks
			buying = self.rt_search.buying_stocks
			
			msg = "📊 종목 상태 리포트\n\n"
			
			msg += f"🚫 재매수 금지 종목 ({len(stocks)}개):\n"
			if stocks:
				msg += ", ".join(stocks) + "\n"
			else:
				msg += "(없음)\n"
			
			msg += f"\n🔄 매수 진행 중 ({len(buying)}개):\n"
			if buying:
				msg += ", ".join(buying) + "\n"
			else:
				msg += "(없음)\n"
				
			# [New] 최근 매도 이력 (5개) - DB에서 조회
			try:
				# 봇 모드 결정 (MOCK / PAPER / REAL)
				use_mock = get_setting('use_mock_server', True)
				if use_mock: mode_str = "MOCK"
				else:
					is_paper = get_setting('is_paper_trading', True)
					mode_str = "PAPER" if is_paper else "REAL"
				
				db_logs = get_trading_logs_from_db(mode=mode_str, limit=5)
				sells = db_logs.get('sells', [])
				
				if sells:
					msg += f"\n📜 최근 매도 이력 ({len(sells)}건):\n"
					for item in sells:
						formatted_time = item['time'][5:] if len(item['time']) > 5 else item['time']
						msg += f"- {formatted_time} {item['name']} ({item['qty']}주) {item['profit_rate']}% [{item['reason']}]\n"
				else:
					msg += "\n📜 매도 이력이 없습니다.\n"
			except Exception as e:
				msg += f"\n(매도 이력 DB 조회 실패: {e})\n"

			tel_send(msg)
			return True
		except Exception as e:
			tel_send(f"❌ status 명령어 오류: {e}")
			return False

	async def reset(self):
		"""매수 금지 목록을 강제로 초기화합니다."""
		try:
			count = len(self.rt_search.purchased_stocks)
			self.rt_search.purchased_stocks.clear()
			tel_send(f"✅ 재매수 금지 목록을 초기화했습니다. (삭제된 종목: {count}개)")
			logger.info(f"사용자 요청으로 매수 금지 목록 초기화됨 (삭제: {count}개)")
			return True
		except Exception as e:
			tel_send(f"❌ reset 명령어 오류: {e}")
			return False

	async def sellall(self):
		"""보유 중인 모든 종목을 매도합니다."""
		try:
			# check_n_sell 백그라운드 태스크가 돌고 있다면 잠시 멈추는 게 좋을 수 있지만
			# 시장가 매도이므로 크게 문제되진 않습니다.
			
			count, sold_list = await asyncio.get_event_loop().run_in_executor(
				None, sell_all_stocks, self.token
			)
			
			if sold_list:
				# 매도된 종목을 매수 금지 목록에서 제거
				for stock in sold_list:
					self.rt_search.purchased_stocks.discard(stock)
					self.rt_search.register_sold_stock(stock)
				
				tel_send(f"🏁 전량 매도 완료: 총 {count}개 종목 매도 주문됨")
			else:
				tel_send("ℹ️ 매도할 종목이 없거나 실패했습니다.")
			
			# 전량 매도 후 봇 정지
			tel_send("🛑 전량 매도 명령에 따라 봇을 정지합니다.")
			await self.stop(True)
				
			return True
		except Exception as e:
			tel_send(f"❌ sellall 명령어 오류: {e}")
			return False

	async def analyze(self):
		"""수학적 분석 엔진을 실행하여 결과를 리포팅합니다."""
		try:
			from math_analyzer import get_analysis_report
			report = get_analysis_report()
			tel_send(report)
			return True
		except Exception as e:
			logger.error(f"분석 실행 중 오류: {e}")
			tel_send(f"❌ 분석 실행 중 오류: {e}")
			return False

	async def reset_asset(self):
		"""기준 자산(initial_asset)을 현재 자산으로 강제 리셋합니다."""
		try:
			token = self.token
			if not token:
				tel_send("❌ 토큰이 없습니다. 다시 시작하거나 잠시 후 시도해주세요.")
				return False
				
			_, _, deposit_amt = await asyncio.get_event_loop().run_in_executor(
				None, get_balance, 'N', '', token
			)
			stock_eval = await asyncio.get_event_loop().run_in_executor(
				None, get_total_eval_amt, token
			)
			current_asset = deposit_amt + stock_eval
			
			if current_asset <= 1000:
				tel_send("❌ 자산 조회 결과가 비정상(0원)입니다. 리셋을 취소합니다.")
				return False
				
			self.initial_asset = current_asset
			today_str = datetime.datetime.now().strftime('%Y-%m-%d')
			with open(self.daily_asset_path, 'w', encoding='utf-8') as f:
				json.dump({'date': today_str, 'asset': current_asset}, f)
				
			logger.info(f"🔄 사용자 요청으로 기준 자산을 {current_asset:,.0f}원으로 리셋했습니다.")
			tel_send(f"✅ 기준 자산을 현재 자산({current_asset:,.0f}원)으로 리셋했습니다. 이제부터 이 금액을 기준으로 수익/손실을 계산합니다.")
			return True
		except Exception as e:
			logger.error(f"reset_asset 오류: {e}")
			tel_send(f"❌ reset_asset 중 오류: {e}")
			return False

	async def _init_daily_asset(self):
		"""일일 시초 자산을 초기화하거나 로드합니다."""
		# [OVERRIDE] 5억으로 강제 고정
		self.initial_asset = 500000000
		logger.info(f"금일 시초 자산 고정: {self.initial_asset:,.0f}원 (5억)")
		return

	async def _handle_set_command(self, key, value_str):
		"""set 명령어를 처리하는 내부 함수"""
		try:
			# 유효성 검사 룰 가져오기
			rules = SettingsValidator.VALIDATION_RULES
			
			if key not in rules:
				tel_send(f"❌ 존재하지 않는 설정입니다: {key}")
				return False
				
			# 타입 변환 및 검증 logic
			rule = rules[key]
			real_value = value_str
			
			try:
				# Bool 처리
				if rule['type'] == bool:
					val_lower = value_str.lower()
					if val_lower in ['true', 'on', 'yes', '1']: real_value = True
					elif val_lower in ['false', 'off', 'no', '0']: real_value = False
					else: raise ValueError("True/On 또는 False/Off여야 합니다.")
				# Int/Float 처리
				elif rule['type'] == int:
					real_value = int(value_str)
				elif rule['type'] == float:
					real_value = float(value_str)
				elif isinstance(rule['type'], tuple):
					if int in rule['type'] and float in rule['type']:
						real_value = float(value_str)
				
				# Range Check
				if 'min' in rule and real_value < rule['min']:
					tel_send(f"❌ 최소값({rule['min']}) 미만입니다.")
					return False
				if 'max' in rule and real_value > rule['max']:
					tel_send(f"❌ 최대값({rule['max']}) 초과입니다.")
					return False
					
				# 저장
				if set_setting(key, real_value):
					tel_send(f"✅ 설정 변경 완료: {key} = {real_value}")
					logger.info(f"설정 변경(Telegram): {key} -> {real_value}")
					return True
				else:
					tel_send("❌ 설정 저장에 실패했습니다. 로그를 확인하세요.")
					return False
					
			except ValueError:
				tel_send(f"❌ 올바른 형식이 아닙니다. 필요 타입: {rule['type']}")
				return False
				
		except Exception as e:
			tel_send(f"❌ 오류 발생: {e}")
			return False

	async def run_sell_logic(self, my_stocks=None, deposit_amt=None, outstanding_orders=None):
		"""매도 로직을 실행합니다 (bot.py 메인 루프에서 호출)"""
		if not self.token:
			return
		
		try:
			# [Fix] Sequential/Injected data to avoid redundant API calls
			# [Realtime] Pass real-time prices for instant update
			current_prices = getattr(self.rt_search, 'current_prices', {})
			
			loop = asyncio.get_running_loop()
			success, sold_stocks, holdings_codes, sell_reasons = await loop.run_in_executor(
				None, chk_n_sell, self.token, self.held_since, my_stocks, deposit_amt, outstanding_orders, current_prices
			)
			
			if success and sold_stocks:
				# 매도된 종목들을 내부 목록에서 제거
				for stock_code in sold_stocks:
					self.rt_search.purchased_stocks.discard(stock_code)
					self.rt_search.register_sold_stock(stock_code)
					
					# [Time-Cut Fix] held_since에서도 제거 (타이머 정리)
					if hasattr(self, 'held_since') and stock_code in self.held_since:
						del self.held_since[stock_code]
						logger.info(f"[Time-Cut] {stock_code} 타이머 삭제 (매도 완료)")
					
					# [Time-Cut Cooldown] 매도 사유가 Time-Cut인 경우 쿨다운 등록
					reason = sell_reasons.get(stock_code, "")
					if reason.startswith("TimeCut"):
						if hasattr(self.rt_search, 'time_cut_cooldown'):
							self.rt_search.time_cut_cooldown[stock_code] = time.time()
							logger.info(f"[Cooldown 등록] {stock_code}: Time-Cut 매도로 인해 재매수 금지 (테스트 90초)")
							
					logger.info(f"매도 완료: {stock_code} (사유: {reason})")
				
				# [Time-Cut Fix] 매도로 슬롯이 비었으면 신규 매수 트리거
				try:
					target_cnt = float(get_setting('target_stock_count', 5))
					current_cnt = len(self.rt_search.purchased_stocks)
					if current_cnt < target_cnt:
						logger.info(f"[Re-entry] 슬롯 발생 ({current_cnt}/{int(target_cnt)}) -> 신규 매수 트리거 (조건식 재요청 포함)")
						# [Fix] 큐가 비어있을 수 있으므로 조건식 재요청을 먼저 보냄
						await self.rt_search.request_condition_search()
						# 잠시 대기 후 프로세서 가동 (데이터 수신 대기)
						await asyncio.sleep(1)
						asyncio.create_task(self.rt_search.process_candidates(current_cnt, target_cnt))
				except Exception as e:
					logger.error(f"[Re-entry] 신규 매수 트리거 실패: {e}")
		
		except Exception as e:
			logger.error(f"매도 로직 실행 중 오류: {e}")

	async def monitor_safety(self, deposit_amt=None, current_stocks=None):
		"""안전 조건을 모니터링하고 필요 시 전량 매도 및 중지합니다."""
		if not self.token:
			return

		try:
			# 1. 시초 자산 확인
			if self.initial_asset is None:
				await self._init_daily_asset()
				if self.initial_asset is None: 
					return

			try:
				# 2. 시간 컷 (Liquidation Time)
				is_mock = get_setting('use_mock_server', False)
				if not is_mock:
					# Real 모드에서만 시간 청산
					liq_hour, liq_minute = MarketHour.get_liquidation_time()
					liq_time = f"{liq_hour:02d}:{liq_minute:02d}"
					if not self.liquidation_done and MarketHour.is_time_passed(liq_time) and MarketHour.is_market_open_time():
						self.liquidation_done = True
						logger.warning(f"⏰ 자동 청산 시간({liq_time}) 도달! 전량 매도를 실행합니다.")
						tel_send(f"⏰ 자동 청산 시간({liq_time})이 되어 전량 매도를 시작합니다.")
						
						try:
							count, sold_list = await asyncio.get_event_loop().run_in_executor(
								None, sell_all_stocks, self.token
							)
							if sold_list:
								for stock in sold_list:
									self.rt_search.purchased_stocks.discard(stock)
									self.rt_search.register_sold_stock(stock)
								tel_send(f"🏁 자동 청산 완료: 총 {count}개 종목 매도됨 (봇은 계속 실행 중)")
						except Exception as e:
							logger.error(f"자동 청산 중 오류: {e}")
					return

				# 3. 자산 손익 체크
				current_asset = 0
				
				# API 호출 최적화: 외부 데이터 사용
				if deposit_amt is not None and current_stocks is not None:
					stock_eval = 0
					for stock in current_stocks:
						try:
							if 'evlu_amt' in stock and stock['evlu_amt']:
								stock_eval += int(float(str(stock['evlu_amt']).replace(',','')))
							elif 'cur_prc' in stock and 'rmnd_qty' in stock:
								prc = int(float(str(stock.get('cur_prc', 0)).replace(',','')))
								qty = int(float(str(stock.get('rmnd_qty', 0)).replace(',','')))
								stock_eval += prc * qty
						except: pass
					current_asset = deposit_amt + stock_eval
				else:
					# Fallback
					_, _, d_amt = await asyncio.get_event_loop().run_in_executor(None, get_balance, 'N', '', self.token)
					s_eval = await asyncio.get_event_loop().run_in_executor(None, get_total_eval_amt, self.token)
					current_asset = d_amt + s_eval
				
				# [Asset Offset]
				asset_offset = int(get_setting('asset_offset', 0))
				if asset_offset != 0:
					current_asset += asset_offset
				
				profit_amt = current_asset - self.initial_asset
				profit_rate = (profit_amt / self.initial_asset) * 100 if self.initial_asset > 0 else 0
				
				if current_asset == 0 and self.initial_asset > 0:
					return # API 오류 무시
				
				# 3-1. 글로벌 손실 제한
				# [Fix] Mock 모드에서는 손실 한도로 인한 자동 종료 방지 (테스트 목적)
				is_mock = get_setting('use_mock_server', False)
				
				global_loss_limit = float(get_setting('global_loss_rate', -99.0))
				
				# 매수 직후 60초간 예외 처리
				is_buying_recent = False
				current_ts = time.time()
				for buy_ts in self.rt_search.buy_last_time.values():
					if current_ts - buy_ts < 60:
						is_buying_recent = True
						break
				
				if is_buying_recent:
					global_loss_limit = -999.0

				if not is_mock and profit_rate <= global_loss_limit:
					logger.warning(f"📉 [LASTTRADE] 일일 손실 한도 초과 감지! ({profit_rate:.2f}% <= {global_loss_limit}%)")
					tel_send(f"📉 [LASTTRADE] 일일 손실 한도({global_loss_limit}%)에 도달하여 전량 매도 및 종료합니다.")
					await self.sellall()
					return

				# 3-2. 목표 수익 달성
				target_profit = int(get_setting('target_profit_amt', 0))
				if target_profit > 0 and profit_amt >= target_profit:
					logger.warning(f"🎉 [LASTTRADE] 일일 목표 수익 달성! ({profit_amt:,.0f}원)")
					tel_send(f"🎉 [LASTTRADE] 일일 목표 수익({target_profit:,.0f}원)을 달성하여 전량 매도 및 종료합니다! 💰")
					await self.sellall()
					return
					
			except Exception as e:
				logger.error(f"안전 모니터링 로직 내부 오류: {e}")
				
		except Exception as e:
			logger.error(f"monitor_safety 전체 오류: {e}")

	async def process_command(self, text):
		"""텍스트 명령어를 처리합니다."""
		# 텍스트 trim 및 소문자 변환
		command = text.strip().lower()
		
		if command == 'start':
			return await self.start()
		elif command.startswith('/set ') or command.startswith('set '):
			# set 명령어 처리
			parts = text.split()
			if len(parts) == 3:
				return await self._handle_set_command(parts[1], parts[2])
			else:
				tel_send("⚠️ 사용법: /set [설정명] [값]\n예: /set target_profit_amt 1000000")
				return False
		elif command == 'stop':
			return await self.stop(True)  # 사용자 명령이므로 auto_start를 false로 설정
		elif command == 'status':
			return await self.status()
		elif command == 'reset' or command == 'reset_stocks':
			return await self.reset()
		elif command == 'reset_asset':
			return await self.reset_asset()
		elif command == 'sellall' or command == 'sa':
			return await self.sellall()
		elif command == 'report' or command == 'r':
			return await self.report()
		elif command == 'condition':
			return await self.condition()
		elif command.startswith('condition '):
			# condition 명령어 처리
			parts = command.split()
			if len(parts) == 2:
				return await self.condition(parts[1])
			else:
				tel_send("❌ 사용법: condition {번호} (예: condition 0)")
				return False
		elif command == 'help':
			return await self.help()
		elif command.startswith('tpr '):
			# tpr 명령어 처리
			parts = command.split()
			if len(parts) == 2:
				return await self.tpr(parts[1])
			else:
				tel_send("❌ 사용법: tpr {숫자} (예: tpr 5)")
				return False
		elif command.startswith('goal '):
			# goal 명령어 처리 (target_profit_amt)
			parts = command.split()
			if len(parts) == 2:
				return await self._handle_set_command('target_profit_amt', parts[1])
			else:
				tel_send("❌ 사용법: goal {금액} (예: goal 500000)")
				return False
		elif command.startswith('limit '):
			# limit 명령어 처리 (global_loss_rate)
			parts = command.split()
			if len(parts) == 2:
				# 음수 처리 로직 (사용자가 양수로 입력해도 음수로 변환)
				val = parts[1]
				try:
					if float(val) > 0:
						val = str(-float(val))
				except:
					pass
				return await self._handle_set_command('global_loss_rate', val)
			else:
				tel_send("❌ 사용법: limit {비율} (예: limit -3)")
				return False
		elif command.startswith('auto '):
			# auto 명령어 처리 (auto_start)
			parts = command.split()
			if len(parts) == 2:
				return await self._handle_set_command('auto_start', parts[1])
			else:
				tel_send("❌ 사용법: auto {on/off} (예: auto on)")
				return False
		elif command.startswith('slr '):
			# slr 명령어 처리
			parts = command.split()
			if len(parts) == 2:
				return await self.slr(parts[1])
			else:
				tel_send("❌ 사용법: slr {숫자} (예: slr -10)")
				return False
		elif command.startswith('brt '):
			# brt 명령어 처리
			parts = command.split()
			if len(parts) == 2:
				return await self.brt(parts[1])
			else:
				tel_send("❌ 사용법: brt {숫자} (예: brt 3)")
				return False
		elif command.startswith('cnt '):
			parts = command.split()
			if len(parts) == 2:
				return await self._handle_set_command('target_stock_count', parts[1])
			else:
				tel_send("❌ 사용법: cnt {숫자} (예: cnt 5)")
				return False
		elif command.startswith('cap '):
			parts = command.split()
			if len(parts) == 2:
				return await self._handle_set_command('trading_capital_ratio', parts[1])
			else:
				tel_send("❌ 사용법: cap {비율} (예: cap 70)")
				return False
		elif command.startswith('mwp '):
			parts = command.split()
			if len(parts) == 2:
				return await self._handle_set_command('math_min_win_rate', parts[1])
			else:
				tel_send("❌ 사용법: mwp {0.0~1.0} (예: mwp 0.6)")
				return False
		elif command.startswith('msc '):
			parts = command.split()
			if len(parts) == 2:
				return await self._handle_set_command('math_min_sample_count', parts[1])
			else:
				tel_send("❌ 사용법: msc {숫자} (예: msc 10)")
				return False
		elif command.startswith('ssr '):
			parts = command.split()
			if len(parts) == 2:
				return await self._handle_set_command('single_stock_rate', parts[1])
			else:
				tel_send("❌ 사용법: ssr {숫자} (예: ssr 4)")
				return False
		elif command == 'factor' or command == 'f':
			return await self.factor()
		elif command == 'analyze' or command == '분석':
			return await self.analyze()
		else:
			tel_send(f"❓ 알 수 없는 명령어입니다: {text}")
			return False
