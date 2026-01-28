import aiosqlite
import asyncio
import aiohttp
import datetime
import os
import json
import time

# [SYSTEM] FINAL VERSION v2.7 - AI Recommender & Late Market Super Filter Integrated
# v2.7: Added time-based AI score hurdles and hard-stop for late-market new buys.
import sys
import threading
import subprocess
from typing import List, Dict, Optional
from config import telegram_token
from chat_command import ChatCommand
from single_instance import SingleInstance
from logger import logger
from settings_validator import SettingsValidator
from utils import normalize_stock_code
from file_utils import safe_write_json, safe_read_json

from get_setting import get_setting
from market_hour import MarketHour
from database import init_db, log_asset_history, log_price_history, get_watering_step_count_sync

from database_helpers import save_system_status, get_pending_web_command, mark_web_command_completed, save_setting, get_bot_running
# from dashboard import run_dashboard_server # Subprocess로 실행됨
# [Mock Server Integration] Use kiwoom_adapter for automatic Real/Mock API switching
from kiwoom_adapter import fn_kt00004 as get_my_stocks, get_account_data, get_total_eval_amt, get_current_api_mode
from kiwoom_adapter import fn_kt00001 as get_balance
from check_n_buy import chk_n_buy, reset_accumulation_global
from candle_manager import candle_manager
from response_manager import response_manager
from voice_generator import speak
from analyze_tools import get_rsi_for_timeframe

class MainApp:
	def __init__(self):
		self.chat_command = ChatCommand()
		self.loop = None  # To be set in run()
		

			
		self.market_open_notified = False
		self.last_update_id = 0
		self.telegram_url = f"https://api.telegram.org/bot{telegram_token}/getUpdates"
		self.keep_running = True
		self.today_started = False  # 오늘 start가 실행되었는지 추적
		self.today_stopped = False  # 오늘 stop이 실행되었는지 추적
		self.today_learned = False  # [NEW] 오늘 AI 학습이 완료되었는지 추적
		self.last_check_date = None  # 마지막으로 확인한 날짜
		self.last_valid_total_asset = 0 # [안전장치] 마지막으로 확인된 정상 자산 금액
		self.held_since = {} # [Time-Cut] 종목별 최초 보유 시각 추적 {code: timestamp}
		self.last_token_time = 0 # [Token Renewal] 마지막 토큰 발급 시각
		self.last_token_date = None # [Token Renewal] 마지막 토큰 발급 날짜
		self.api_fail_count = 0     # [Health Check] 연속 API 실패 횟수
		self.total_api_calls = 0   # [Health Check] 총 API 호출 횟수
		self.total_api_fails = 0   # [Health Check] 총 API 실패 횟수
		self.last_autocancel_time = 0 # [Throttle] AutoCancel 실행 간격 조절
		self.manual_stop = False      # [New] 사용자 수동 정지 여부 추적 (자동 재시작 방지)
		self.last_mock_learn_time = time.time() - 50 # [Mock Learning] 첫 학습을 10초 후 실행하기 위해 50초 전으로 설정

		
		# [Persistent Held Time] - DB 기반
		self.load_held_times()
		
		# [Fix] Mock 모드 시간 오류 보정 (200분 이상 된 건 과거 찌꺼기 데이터이므로 리셋)
		try:
			from kiwoom_adapter import get_current_api_mode
			if get_current_api_mode().upper() == 'MOCK':
				now = time.time()
				for code, t in list(self.held_since.items()):
					if (now - t) > 12000: # 200분(12000초) 이상
						self.held_since[code] = now
						logger.info(f"[Time Fix] {code}: 200분 이상 경과된 과거 데이터 감지 -> 현재 시간으로 리셋")
		except: pass
		
		# [Time-Cut Fix] rt_search에 held_since 참조 전달 (매수 즉시 타이머 등록 가능)
		self.chat_command.rt_search.held_since_ref = self.held_since
		
		# [User Request] 분할 매수 4차 및 물타기 전용 강제 설정
		try:
			from database_helpers import save_setting
			save_setting('split_buy_cnt', 4)
			save_setting('target_stock_count', 5)
			save_setting('single_stock_strategy', 'WATER')
			logger.info("[Settings] 5종목 운영, 분할 매수 4회 & 물타기(WATER) 모드로 강제 설정 완료")
		except: pass
		
		# [Math] response_manager 전달
		self.chat_command.rt_search.response_manager = response_manager
		
		# [Heartbeat]
		self._init_heartbeat()
		
		# [AI Recommender] - New
		from ai_recommender import AIRecommender
		self.ai_recommender = AIRecommender(self._on_ai_recommendation)
		
	def _on_ai_recommendation(self, code, source, ai_score, ai_reason):
		"""AI 모델이 추천한 종목을 매수 대기열에 추가"""
		try:
			# 매수 로직 호출 (소스 명시)
			# 비동기 루프로 스케줄링
			if self.chat_command.token:
				asyncio.run_coroutine_threadsafe(
					self._async_chk_n_buy(code, self.chat_command.token, source, ai_score, ai_reason),
					self.loop
				)
			else:
				logger.warning(f"⚠️ [AI 추천 무시] 토큰 미발급 상태라 매수 불가: {code}")
		except Exception as e:
			logger.error(f"AI 추천 처리 실패: {e}")

	async def _async_chk_n_buy(self, code, token, source, ai_score, ai_reason):
		"""비동기 래퍼"""
		await asyncio.get_event_loop().run_in_executor(
			None, chk_n_buy, code, token, None, None, None, None, None, None, source, ai_score, ai_reason
		)

	def load_held_times(self):
		"""DB에서 보유 시간 로드"""
		try:
			from database_helpers import get_all_held_times
			self.held_since = get_all_held_times()
			logger.info(f"보유 시간 DB 로드 완료: {len(self.held_since)}개 종목")
		except Exception as e:
			logger.error(f"보유 시간 DB 로드 실패: {e}")
			self.held_since = {}

	# [Heartbeat] 소켓 초기화
	def _init_heartbeat(self):
		import socket
		self.hb_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		# self.hb_sock.setblocking(False) # Non-blocking
		self.hb_addr = ('127.0.0.1', 5005)
		self.last_hb_time = 0

	def _send_heartbeat(self):
		"""도그에게 생존 신고 (UDP 패킷 전송)"""
		try:
			now = time.time()
			if now - self.last_hb_time > 2.0: # 2초마다 전송
				msg = json.dumps({
					"status": "alive",
					"timestamp": now,
					"pid": os.getpid()
				}).encode('utf-8')
				self.hb_sock.sendto(msg, self.hb_addr)
				self.last_hb_time = now
		except Exception as e:
			# logger.debug(f"Heartbeat error: {e}")
			pass

	def save_held_times(self):
		"""DB에 보유 시간 저장"""
		try:
			from database_helpers import save_held_time
			for code, held_since in self.held_since.items():
				save_held_time(code, held_since)
		except Exception as e:
			logger.error(f"보유 시간 DB 저장 실패: {e}")
		
	async def get_chat_updates(self):
		"""텔레그램 채팅 업데이트를 가져옵니다."""
		try:
			params = {
				'offset': self.last_update_id + 1,
				'timeout': 1
			}
			
			async with aiohttp.ClientSession() as session:
				async with session.get(self.telegram_url, params=params) as response:
					data = await response.json()
			
			if data.get('ok'):
				updates = data.get('result', [])
				for update in updates:
					self.last_update_id = update['update_id']
					
					if 'message' in update and 'text' in update['message']:
						text = update['message']['text']
						logger.info(f"텔레그램 메시지 수신: {text}")
						return text
			return None
		except aiohttp.ClientError as e:
			logger.error(f"텔레그램 API 연결 오류: {e}")
			return None
		except Exception as e:
			logger.error(f"채팅 업데이트 가져오기 실패: {e}", exc_info=True)
			return None
	

	async def check_market_timing(self):
		"""장 시작/종료 시간 및 기타 주기적 이벤트 체크"""
		# 0. 휴장일(주말/공휴일) 체크 -> 엔진은 돌리되 매매 로직만 스킵
		if not MarketHour.is_trading_day():
			# Mock 모드면 휴장일이라도 거래 허용 (테스트용)
			if not get_setting('use_mock_server', False):
				if int(time.time()) % 3600 < 5: # 1시간에 한 번만 출력
					logger.info("💤 오늘은 휴장일입니다. 시스템은 생존 보고(Heartbeat) 중입니다.")
				return

		auto_start = get_setting('auto_start', False)
		today = MarketHour.get_today_date()
		
		# 새로운 날이 되면 플래그 리셋
		if self.last_check_date != today:
			self.today_started = False
			self.today_stopped = False
			self.today_learned = False # [NEW] 학습 플래그 리셋
			self.market_open_notified = False # [Fix] 장전 알림 플래그 리셋
			self.manual_stop = False # [Fix] 날짜 변경 시 수동 정지 플래그 해제 (자동 시작 보장)
			self.last_check_date = today
			
			# [NEW] 새로운 날 시작 시 전일 데이터 정리 (Non-blocking)
			logger.info("🧹 새로운 날 감지 - 전일 데이터 정리 시작")
			def run_cleanup():
			    try:
			        import subprocess
			        import sys
			        subprocess.run([sys.executable, 'cleanup_daily.py'], cwd=os.path.dirname(os.path.abspath(__file__)), timeout=60)
			        logger.info("✅ 전일 데이터 정리 완료")
			    except Exception as e:
			        logger.error(f"⚠️ 데이터 정리 오류: {e}")
			
			asyncio.get_event_loop().run_in_executor(None, run_cleanup)

			# [AI Smart Count] 장 시작 시 예산에 맞게 종목 수 자동 최적화
			self._optimize_stock_count_by_budget()

			# [Auto Tuning] 예산에 맞게 분할 매수 횟수(Step) 자동 최적화 (사장님 요청 기능)
			try:
				result = subprocess.run([sys.executable, 'optimize_settings.py'], cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True, timeout=30)
				if result.stdout: logger.info(f"[AutoTune] {result.stdout.strip()}")
			except Exception as e: 
				logger.error(f"[AutoTune] 실행 실패: {e}")
		
		# 1. 자동 시작 처리
		# Mock 모드이거나 장중이면 자동 시작
		# [Mod] 사용자 요청: "프로그램 시작하면 자동시작 되어야 함"
		# 따라서 Mock 모드일 때는 manual_stop 여부와 상관없이 초기 1회는 무조건 시작 시도
		
		# [Fix] 인자값 무시하고 DB 설정값 강제 로드 (확실한 자동시작)
		auto_start = get_setting('auto_start', True)
		
		# [Debug] 콘솔 출력으로 원인 파악
		is_mock = get_setting('use_mock_server', False)
		target_condition = (is_mock or MarketHour.is_market_open_time())
		
		logger.info(f"🤖 [AutoStart Debug] auto_start={auto_start}, is_mock={is_mock}, target={target_condition}, manual_stop={self.manual_stop}")
		
		if auto_start and target_condition:
			logger.info(f"🚀 [AutoStart Debug] connected={self.chat_command.rt_search.connected}, today_started={self.today_started}")
			if not self.chat_command.rt_search.connected:
				logger.info(f"🚀 자동 시작 조건 만족 (Mock={is_mock}) - start 명령 실행")
				success = await self.chat_command.start()
				if success:
					self.today_started = True 
					self.manual_stop = False
					logger.info("✅ [AutoStart] start() 명령 실행 완료")
				else:
					logger.info("❌ [AutoStart] start() 명령 실행 실패 (다음 루프 재시도)")
			elif not self.today_started:
				self.today_started = True
				logger.info("ℹ️ [AutoStart] 이미 실행 중임 (상태 동기화)")
		else:
			if not self.today_started:
				logger.info("💤 [AutoStart] 조건 불만족. 대기합니다.")
			
			# 장전인데 아직 플래그가 안 켜졌으면 (로그 출력용)
			if not self.market_open_notified:
				logger.info(f"자동 시작 대기 중 - 장 시작 시 자동으로 연결됩니다.")
				self.market_open_notified = True # 메시지 중복 방지용
		
		# 2. 장 종료 처리 (매도 및 정지) - 15시 이후에만 동작하도록 시간 가드 추가
		is_mock = (get_current_api_mode() == "Mock")
		now = datetime.datetime.now()
		now_hour = now.hour
		now_min = now.minute
		
		# [Critical Fix] 아침(9시)에 장 종료 로직이 오작동하는 것을 방지하기 위해 15시(오후) 조건 추가
		if not is_mock and now_hour >= 15 and MarketHour.is_market_end_time() and not self.today_stopped:
			logger.info(f"장 종료 시간({MarketHour.MARKET_END_HOUR:02d}:{MarketHour.MARKET_END_MINUTE:02d})입니다. 자동으로 stop 명령을 실행합니다.")
			await self.chat_command.stop(False)  # auto_start를 false로 설정하지 않음
			logger.info("자동으로 계좌평가 보고서를 발송합니다.")
			await self.chat_command.report()  # 장 종료 시 report도 자동 발송
			self.today_stopped = True  # 오늘 stop 실행 완료 표시


		# 3. [NEW] 일일 AI 학습 실행 (정확히 15:40분 시스템 타겟)
		# 장 종료(15:30) 후 데이터가 모두 정산된 시점인 15:40분에 학습 시작
		# [Debug] AI 학습 진입 조건 체크
		if now_hour == 15 and now_min >= 40 and not self.today_learned:
			# [Fix] Scope 문제 방지를 위해 로컬 임포트 및 존재 확인
			from get_setting import get_setting as _get_setting
			from market_hour import MarketHour as _MH
			
			logger.info(f"🔍 [AI 학습 체크] 시간: {now_hour}:{now_min}, 오늘학습여부: {self.today_learned}")
			# DB에서 한 번 더 확인 (중복 실행 방지)
			is_actually_learned = _get_setting('ai_learned_today', '') == str(_MH.get_today_date())
			
			if not is_actually_learned:
				self.today_learned = True # 즉시 플래그 세워 중복 진입 차단
				logger.info("🤖 [AI 학습] 정기 학습 시각(15:40) 도달 - 백그라운드 실행 시작")
				
				def run_learning():
				    try:
				        import subprocess
				        import sys
				        import re
				        # 타임아웃 10분, 결과 캡처
				        result = subprocess.run([sys.executable, 'learn_daily.py'], 
				                               cwd=os.path.dirname(os.path.abspath(__file__)), 
				                               capture_output=True, text=True, timeout=600)
				        
				        if result.returncode == 0:
				            # 로그에서 건수 추출 (예: "당일 거래: 61건", "당일 시그널: 31455건")
				            trades = re.search(r'당일 거래: (\d+)건', result.stdout)
				            signals = re.search(r'당일 시그널: (\d+)건', result.stdout)
				            t_cnt = trades.group(1) if trades else "?"
				            s_cnt = signals.group(1) if signals else "?"
				            
				            logger.info(f"✅ [AI 정기 학습 완료] 데이터 총량 -> 거래: {t_cnt}건, 시그널: {s_cnt}건")
				            from database_helpers import save_setting
				            save_setting('ai_learned_today', str(_MH.get_today_date()))
				        else:
				            logger.error(f"⚠️ [AI 학습] 실행 실패 (Code {result.returncode}): {result.stderr}")
				            self.today_learned = False
				    except Exception as e:
				        logger.error(f"⚠️ [AI 학습] 프로세스 오류: {e}")
				        self.today_learned = False
				
				asyncio.get_event_loop().run_in_executor(None, run_learning)
			else:
				self.today_learned = True
		
		# 3-1. [Mock 전용] 5분 단위 정기 학습 (사용자 요청: Mock 모드 시 5분 마다 학습)
		if is_mock:
			now_ts = time.time()
			if now_ts - self.last_mock_learn_time >= 300: # 300초 = 5분
				logger.info(f"🧪 [Mock AI 학습] 5분 주기 학습 시점 도달 - 백그라운드 실행")
				self.last_mock_learn_time = now_ts
				
				def run_mock_learning():
					try:
						import subprocess
						import sys
						import re
						result = subprocess.run([sys.executable, 'learn_daily.py'], 
									cwd=os.path.dirname(os.path.abspath(__file__)), 
									capture_output=True, text=True, timeout=300)
						
						if result.returncode == 0:
							trades = re.search(r'당일 거래: (\d+)건', result.stdout)
							signals = re.search(r'당일 시그널: (\d+)건', result.stdout)
							t_cnt = trades.group(1) if trades else "?"
							s_cnt = signals.group(1) if signals else "?"
							logger.info(f"✅ [Mock AI 학습 완료] 분석 결과 -> 거래: {t_cnt}건, 시그널: {s_cnt}건")
						else:
							logger.error(f"⚠️ [Mock AI 학습] 실패: {result.stderr}")
					except Exception as e:
						logger.error(f"⚠️ [Mock AI 학습] 프로세스 오류: {e}")
				
				asyncio.get_event_loop().run_in_executor(None, run_mock_learning)
		
		# 4. [NEW] 시간 기반 자동 모드 전환 (Mock ↔ Real)
		await self.check_auto_mode_switch()
	
	async def check_auto_mode_switch(self):
		"""시간 기반 Mock ↔ Real 자동 전환"""
		try:
			# 설정 확인
			auto_switch_enabled = get_setting('auto_mode_switch_enabled', False)  # 기본값: 비활성화 (수동 전환 원칙)
			if not auto_switch_enabled:
				return
			
			now = datetime.datetime.now()
			current_time = now.strftime('%H:%M')
			
			# 전환 시간 설정 (기본값)
			real_switch_time = get_setting('real_mode_switch_time', '09:00')
			mock_switch_time = get_setting('mock_mode_switch_time', '15:30')
			
			# 현재 모드 확인
			current_mode = get_current_api_mode()
		
			if not MarketHour.is_trading_day():
				return  # 휴장일에는 자동 전환 스킵
		
			# [Mod] 수동 변경 감지 로직 제거 (사용자 의도: 일단 전환 후 시간 체크에 따라 처리)
			# last_manual_update = float(get_setting('last_manual_setting_update', 0))
			# if time.time() - last_manual_update < 300: ...


			# Mock → Real 전환 (장 시작 시간 이후 & 아직 Mock인 경우)
			# [Fix] 단순 == 비교 대신 >= 비교로 변경하여 봇이 늦게 켜져도 전환되도록 함 (단, 점심시간 전까지만)
			if real_switch_time <= current_time < "12:00" and current_mode == "Mock":
				logger.info(f"🔄 [{current_time}] 자동 전환: Mock → Real (실전 매매 시작)")
				from database_helpers import save_setting
				save_setting('use_mock_server', False)
				save_setting('trading_mode', 'REAL')
				
				# API 어댑터 재설정 (즉시 반영)
				from kiwoom_adapter import reset_api
				reset_api()
				
				# [Fix] 토큰 리셋 (재로그인 유도)
				self.chat_command.token = None
				
				# [AI Smart Count] Real 모드 진입 시 예산 최적화 즉시 실행
				self._optimize_stock_count_by_budget()
				
				logger.info("✅ Real 서버로 전환 완료 - 실전 매매 활성화")
				
				# [Fix] 엔진 재시작 및 플래그 초기화 (중요: REAL 시그널 수신을 위함)
				self.today_started = False
				self.manual_stop = False
				save_setting('auto_start', True)
				
				# 기존 검색 엔진 정지 (그래야 다음 루프에서 start()가 호출됨)
				if self.chat_command.rt_search.connected:
					logger.info("🔄 기존 검색 엔진(Mock) 중지 중...")
					await self.chat_command.rt_search.stop()
			
			# Real → Mock 전환 (장 마감 시간 이후 & 아직 Real인 경우)
			elif current_time >= mock_switch_time and current_mode != "Mock":
				logger.info(f"⚠️ [{current_time}] 장 시간이 아닙니다. Mock 모드로 자동 전환합니다.")
				
				from database_helpers import save_setting
				save_setting('use_mock_server', True)
				save_setting('trading_mode', 'MOCK')
				
				# [AI Smart Count] Mock 모드에서는 테스트를 위해 종목 수 넉넉히 복구 (기본 5개)
				save_setting('target_stock_count', 5)
				logger.info("🧪 [Mock 모드] 테스트 환경을 위해 목표 종목 수를 5개로 재설정했습니다.")
				
				# [Fix] Mock 복귀 시 Auto Start 활성화
				self.manual_stop = False
				save_setting('auto_start', True)
				
				# API 어댑터 재설정
				from kiwoom_adapter import reset_api
				reset_api()
				
				# [Fix] 토큰 리셋
				self.chat_command.token = None
				
				logger.info("✅ Mock 서버로 전환 완료 - 테스트 모드 복귀")
				
				# [Fix] 엔진 재시작 유도
				self.today_started = False
				self.manual_stop = False
				save_setting('auto_start', True)
				
				# 기존 검색 엔진 정지
				if self.chat_command.rt_search.connected:
					logger.info("🔄 기존 검색 엔진(Real) 중지 중...")
					await self.chat_command.rt_search.stop()
		
		except Exception as e:
			logger.error(f"⚠️ 자동 모드 전환 오류: {e}")

	async def check_web_command(self):
		"""웹 대시보드에서 보낸 명령을 확인하고 처리합니다. (DB 기반)"""
		try:
			# [Fix] 함수 시작 부분에서 미리 import하여 Scope 문제 방지
			from database_helpers import mark_web_command_completed, save_setting, set_bot_running

			cmd_info = get_pending_web_command()
			if cmd_info:
				command = cmd_info.get('command')
				cmd_id = cmd_info.get('id')
				
				logger.info(f"🚀 [Web Dashboard] 명령 수신됨 (DB): {command}")
				
				if command == 'reinit':
					# [환경 전환] 서버 모드 또는 키 변경 시 전체 재초기화
					logger.info("🔄 [System] 서버 모드 전환 감지 - 전체 재초기화 시작")
					self.chat_command.token = None # 토큰 리셋 (재로그인 유도)
					self.chat_command.get_token()  # 새로운 모드/키로 로그인
					
					# 실시간 검색 재연결 및 강제 시작 (새로운 API 환경에 맞게)
					if self.chat_command.rt_search.connected:
						await self.chat_command.rt_search.stop()
						await asyncio.sleep(1)
					
					# 새로운 토큰으로 시작 시도
					success = await self.chat_command.rt_search.start(self.chat_command.token)
					if success:
						self.today_started = True # 시작 성공 마킹
						self.manual_stop = False # 수동 일시정지 해제
						set_bot_running(True)    # DB 상태 동기화
						logger.info(f"✅ [System] 새로운 모드({get_current_api_mode()})로 자동 시작 성공")
					else:
						logger.error(f"❌ [System] 새로운 모드({get_current_api_mode()})로 시작 실패")

					# 누적 매수 금액 리셋
					from check_n_buy import reset_accumulation_global
					reset_accumulation_global()
					
					mark_web_command_completed(cmd_id) # 중요: 명령 처리 완료 마킹
					
					# [Immediate Refresh] 즉시 데이터 갱신하여 UI 반영
					logger.info("🔄 [System] 데이터 즉시 갱신 중...")
					loop = asyncio.get_running_loop()
					stocks, bal, bal_data = await self._update_market_data(loop)
					if stocks is not None:
						await self._update_status_json(stocks, bal_data, bal)
					
					logger.info("✅ [System] 재초기화 및 데이터 동기화 완료.")
					
				elif command == 'report':
					# 웹에서 리포트 요청 시 텔레그램 발송 없이 JSON만 업데이트
					try:
						await self.chat_command.report(send_telegram=False)
					finally:
						mark_web_command_completed(cmd_id)
					
				else:
					# 시작/종료 명령 시 즉시 로그 출력
					if command == 'stop':
						self.manual_stop = True
						save_setting('auto_start', 'false')
						set_bot_running(False)
						logger.info("🛑 [Web Command] 봇을 일시정지(Paused) 합니다.")
					elif command == 'start':
						self.manual_stop = False
						save_setting('auto_start', 'true')
						set_bot_running(True)
						logger.info("🚀 [Web Command] 봇을 재개(Resumed) 합니다.")
						
					# 공통 처리 완료 표시
					mark_web_command_completed(cmd_id)
					return # 직접 처리했으므로 process_command 호출 생략 (충돌 방지)
					
				# 처리 완료 표시
				mark_web_command_completed(cmd_id)
		except Exception as e:
			logger.error(f"❌ 웹 명령 처리 중 오류: {e}")

	async def _update_market_data(self, loop):
		"""API에서 계좌/잔고 정보를 가져오고 실시간 현재가를 패치합니다 (Refactoring Helper)"""
		# [Fix] Sequential API calls to avoid Error 1700 (Rate Limit)
		try:
			self.total_api_calls += 1
			
			# 1. 보유 종목 조회
			# logger.debug("API 요청: get_account_data")
			acnt_data = await loop.run_in_executor(None, get_account_data, 'N', '', self.chat_command.token)
			if acnt_data and acnt_data[1]: # 요약 데이터(summary)가 있어야 정상 응답
				current_stocks, acnt_summary = acnt_data
			else:
				# [Fix] 요약 데이터가 없으면 API 실패로 간주하여 빈 리스트로 덮어쓰지 않음
				# (단, RealKiwoomAPI가 실패 시 ([], {})를 반환하므로 이를 감지)
				logger.warning("[API Warning] 보유 종목 조회 실패 (Empty Summary) -> 기존 상태 유지")
				current_stocks, acnt_summary = None, None
				
			# 2. 짧은 대기 (호출 집중 방지)
			await asyncio.sleep(0.5)
			
			# 3. 예수금/잔고 조회
			# logger.debug("API 요청: get_balance")
			current_balance = await loop.run_in_executor(None, get_balance, 'N', '', self.chat_command.token)
			
			# [센스: 데이터 검증] 데이터가 정상적으로 왔는지 체크
			if current_balance is None or (current_balance[0] == 0 and current_balance[2] == 0 and not current_stocks):
				raise Exception("API returned empty/null data")
				
			self.api_fail_count = 0 # 성공 시 카운트 리셋
		except Exception as e:
			self.api_fail_count += 1
			self.total_api_fails += 1
			
			# Mock 모드에서는 Health Check 경고 표시 안 함
			use_mock = get_setting('use_mock_server', False)
			if not use_mock:
				logger.error(f"[Health Check] API 통신 실패 ({self.api_fail_count}회 연속): {e}")
			
			# 5회 연속 실패 시 텔레그램 알림 (Mock 모드 제외)
			if self.api_fail_count == 5 and not use_mock:
				from tel_send import tel_send
				tel_send(f"⚠️ [긴급] 키움 API 통신이 5회 연속 실패 중입니다. 조치가 필요할 수 있습니다. (장애 여부 확인 요망)")
			
			return None, None, None # 실패 시 빈 값 반환
		
		# Balance Data 구조화
		balance_data = None
		if current_balance:
			# current_balance: (ord_alow, tot_evlu_amt, deposit)
			balance_data = {
				'balance': current_balance[0],
				'deposit': current_balance[2],
				'net_asset': current_balance[2] + current_balance[1] 
			}

		# 2. 실시간 가격 패치 (Real-time Price Patching)
		if current_stocks and self.chat_command.rt_search.current_prices:
			for stock in current_stocks:
				code = normalize_stock_code(stock.get('stk_cd', ''))
				if code in self.chat_command.rt_search.current_prices:
					new_price = self.chat_command.rt_search.current_prices[code]
					try:
						curr_qty = int(stock.get('rmnd_qty', '0'))
						avg_price = float(stock.get('avg_prc', stock.get('pchs_avg_pric', '0')))
						
						# 값 갱신
						stock['cur_prc'] = str(new_price)
						
						# 파생 값 재계산
						if curr_qty > 0 and avg_price > 0:
							new_eval = new_price * curr_qty
							new_pl = (new_price - avg_price) * curr_qty
							new_rate = ((new_price - avg_price) / avg_price) * 100
							
							stock['evlu_amt'] = str(new_eval)
							stock['pl_amt'] = str(int(new_pl))
							stock['pl_rt'] = f"{new_rate:.2f}"
						
						# [Candle] 틱 데이터 추가
						candle_manager.add_tick(code, new_price)
					except: pass
					
		return current_stocks, current_balance, balance_data

	async def _sync_holdings(self, current_stocks, balance_data):
		"""API 데이터와 내부 보유 목록 동기화 (Refactoring Helper)"""
		internal_count = len(self.chat_command.rt_search.purchased_stocks)
		api_count = len(current_stocks) if current_stocks else 0
		
		# [Sync 방어 로직] 
		# API가 '빈 목록'([])을 리턴하고 + 자산도 0원이면 -> 명백한 API 오류로 간주
		check_asset = 0
		if balance_data:
			check_asset = balance_data.get('net_asset', 0)
			
		should_skip_sync = False
		
		# 평가금(Stock Eval) 확인
		eval_amt = 0
		if balance_data:
			eval_amt = balance_data.get('net_asset', 0) - balance_data.get('deposit', 0)

		# 1. 자산도 0이고 목록도 0이면 -> 통신 오류 가능성
		if api_count == 0 and check_asset <= 0:
			logger.warning(f"[Sync 스킵] API 보유종목 0개 & 자산 0원 감지 - 내부 목록 보호를 위해 동기화 생략")
			should_skip_sync = True
		
		# 2. 자산(예수금)은 잡히는데 목록만 0개? (내부는 1개 이상) -> 누락 의심
		elif api_count == 0 and internal_count > 0:
			if eval_amt > 5000: # 평가금액이 존재한다면 API 리스트 누락일 가능성이 큼
				logger.warning(f"[Sync 스킵] API 목록 0개 vs 평가금 {eval_amt:,.0f}원 - API 리스트 누락 의심되어 동기화 생략")
				should_skip_sync = True
		
		# 3. [추가] 부분 누락 탐지 (목표 종목이 여럿인데 일부만 온 경우)
		elif api_count > 0 and api_count < (internal_count - 1):
			# 리스트의 평가금 합산
			list_eval_sum = sum(int(float(str(s.get('evlu_amt', 0)).replace(',',''))) for s in current_stocks)
			# 요약 자산(eval_amt)과 리스트 합산의 차이가 큼 (예: 30% 이상)
			if eval_amt > 0 and list_eval_sum < (eval_amt * 0.7):
				logger.warning(f"[Sync 스킵] API 목록({api_count}개, 합 {list_eval_sum:,.0f}원) vs 요약 평가금({eval_amt:,.0f}원) 괴리 - 부분 누락 의심")
				should_skip_sync = True
		
		if not should_skip_sync:
			self.chat_command.rt_search.update_held_stocks(current_stocks)
			
			# [Time-Cut] 타이머 동기화
			if current_stocks:
				current_codes = {normalize_stock_code(s.get('stk_cd', '')) for s in current_stocks}
				changed = False
				# 신규 추가
				for code in current_codes:
					if code and code not in self.held_since:
						self.held_since[code] = time.time()
						changed = True
						logger.info(f"[Time-Cut] 신규 보유 감지: {code}")
				# 삭제 처리
				from database_helpers import delete_held_time
				for code in list(self.held_since.keys()):
					if code not in current_codes:
						del self.held_since[code]
						delete_held_time(code) # [Fix] DB에서도 삭제 (필수)
						changed = True
						logger.info(f"[Time-Cut] 보유 목록 이탈로 타이머 삭제: {code}")
				if changed: self.save_held_times()

	async def _process_watering_logic(self, current_stocks, balance_data, outstanding_orders=None):
		"""물타기/불타기 조건 체크 로직 (Refactoring Helper)"""
		for stock in current_stocks:
			code = normalize_stock_code(stock.get('stk_cd', ''))
			if code:
				await asyncio.get_event_loop().run_in_executor(
					None, chk_n_buy, code, self.chat_command.token, current_stocks, balance_data, self.held_since, outstanding_orders, response_manager
				)
				await asyncio.sleep(0.05)

	async def _update_status_json(self, current_stocks, balance_data, current_balance):
		"""GUI 표시용 status.json 파일 업데이트 (Refactoring Helper)"""
		# 방어 로직: 내부 보유 중인데 API가 0개면 화면 클리어 방지를 위해 스킵
		internal_count = len(self.chat_command.rt_search.purchased_stocks)
		if (not current_stocks or len(current_stocks) == 0) and internal_count > 0:
			return time.time()

		# 데이터 준비
		deposit = 0
		total_asset = 0 # [Fix] 초기화 추가
		total_eval_sum = 0 # [Fix] 초기화 위치 이동
		
		# 예수금(Deposit) 추출
		if balance_data: 
			try: deposit = int(balance_data.get('deposit', 0) or 0)
			except: deposit = 0
		elif current_balance: 
			try: deposit = int(current_balance[2] or 0)
			except: deposit = 0

		total_pl_sum = 0
		total_buy_sum = 0 # 실매입금 합계
		status_holdings = []

		# 설정 로드
		target_cnt = float(get_setting('target_stock_count', 1)) 
		if target_cnt < 1: target_cnt = 1
		
		# [Sync] 1:1:2:2:4 수열 기반 단계 계산 (Trading Core와 동기화)
		s_cnt = int(get_setting('split_buy_cnt', 5))
		early_stop_step = int(get_setting('early_stop_step', s_cnt - 1))
		if early_stop_step <= 0: early_stop_step = s_cnt

		weights = []
		for i in range(s_cnt):
			# [수정] 1:1:2:2:4 수열 적용
			weight = 2**(i // 2)
			weights.append(weight)
			
		# [Critical Sync] 조기 손절 단계까지만 분모로 사용하여 100% 비중 도달 시점 동기화
		total_weight = sum(weights[:early_stop_step])
		if total_weight <= 0: total_weight = sum(weights)

		cumulative_ratios = []
		curr_s = 0
		for w in weights:
			curr_s += w
			cumulative_ratios.append(curr_s / total_weight)
			
		# [Stable Basis] 원금 기준 자산 추정 (UI 단계 고정용)
		temp_pur_sum = 0
		temp_eval_sum = 0
		if current_stocks:
			for s in current_stocks:
				try:
					# 매입금액 합계
					p_val = 0
					p_raw = str(s.get('pchs_amt', s.get('pur_amt', '0'))).replace(',', '')
					if p_raw != '0': p_val = int(float(p_raw))
					else:
						qty = int(float(str(s.get('rmnd_qty', '0')).replace(',','')))
						avg = float(str(s.get('pchs_avg_pric', s.get('avg_prc','0'))).replace(',',''))
						p_val = int(qty * avg)
					temp_pur_sum += p_val

					# 평가금액 합계
					val = int(float(str(s.get('evlu_amt', '0')).replace(',','')))
					if val == 0: 
						prc = int(float(str(s.get('cur_prc', '0')).replace(',','')))
						qty = int(float(str(s.get('rmnd_qty', '0')).replace(',','')))
						val = prc * qty
					temp_eval_sum += val
				except: pass
		
		# 유저 요청: 원금 기준(Principal Basis)으로 단계 계산 고정
		total_asset_basis = deposit + temp_pur_sum
		total_asset_est = deposit + temp_eval_sum # 실제 자산(평가금)은 별도 보관

		# 실제 매수 로직과 동일하게 배정 금액 계산 (UI 표시용)
		capital_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0

		if int(target_cnt) == 1:
			alloc_per_stock = total_asset_basis * 0.98
		else:
			alloc_per_stock = (total_asset_basis * capital_ratio) / target_cnt

		
		# 분무점 유연성 보정 (95% -> 100% 근사)
		if alloc_per_stock <= 0: alloc_per_stock = 1

		# 종목별 데이터 가공
		if current_stocks:
			for s in current_stocks:
				try:
					# 1. 평가금/손익 계산
					evlu = 0
					val_raw = str(s.get('evlu_amt', '0')).replace(',', '')
					if val_raw != '0': evlu = int(float(val_raw))
					else:
						prc = int(float(str(s.get('cur_prc', '0')).replace(',', '')))
						qty = int(float(str(s.get('rmnd_qty', '0')).replace(',', '')))
						evlu = prc * qty
					
					pl = 0
					pl_raw = str(s.get('pl_amt', s.get('evlu_pfls_amt', '0'))).replace(',', '')
					if pl_raw != '0': pl = int(float(pl_raw))
					else:
						prc = int(float(str(s.get('cur_prc', '0')).replace(',', '')))
						avg = float(str(s.get('pchs_avg_pric', s.get('avg_prc','0'))).replace(',', ''))
						qty = int(float(str(s.get('rmnd_qty', '0')).replace(',', '')))
						if avg > 0: pl = int((prc - avg) * qty)


					# 2. 매입금 누적 (아래 Clean Data 처리 구문에서 통합 처리됨)
					# 3. GUI 아이템 생성 (Clean Data)
					# API 원본 데이터에서 필요한 값만 추출하여 깨끗한 정수/실수형으로 변환
					item = {}
					code = normalize_stock_code(s.get('stk_cd', ''))
					item['stk_cd'] = code
					item['stk_nm'] = s.get('stk_nm', '')
					
					# 수량 (rmnd_qty or hold_qty)
					qty = 0
					try:
						q_str = str(s.get('rmnd_qty', s.get('hold_qty', '0'))).replace(',', '')
						qty = int(float(q_str))
					except: pass
					item['qty'] = qty
					item['rmnd_qty'] = qty # 호환성 유지
					
					# 평균단가 (pchs_avg_pric or avg_prc)
					avg_prc = 0.0
					try:
						ap_str = str(s.get('pchs_avg_pric', s.get('avg_prc', '0'))).replace(',', '')
						avg_prc = float(ap_str)
					except: pass
					item['avg_prc'] = avg_prc
					
					# 현재가 (cur_prc) - 0인 경우 방어
					cur_prc = 0
					try:
						cp_str = str(s.get('cur_prc', '0')).replace(',', '')
						cur_prc = int(float(cp_str))
					except: pass
					
					if cur_prc == 0 and avg_prc > 0:
						# [Fix] 현재가가 0이면(오류) 평단가로 대체하여 수익률 -100% 방지
						cur_prc = int(avg_prc)
						# logger.debug(f"[UI 보정] {code} 현재가 0 -> 평단가({avg_prc})로 임시 대체")
					
					item['cur_prc'] = cur_prc
					
					# 매입금액 (pur_amt or pchs_amt)
					pur_amt = 0
					try:
						pa_str = str(s.get('pchs_amt', s.get('pur_amt', '0'))).replace(',', '')
						pur_amt = int(float(pa_str)) # float -> int
					except:
						# 없을 경우 역산
						if qty > 0 and avg_prc > 0:
							pur_amt = int(avg_prc * qty)
					item['pur_amt'] = pur_amt
					
					# 평가금액 (evlt_amt or evlu_amt)
					evlt_amt = 0
					try:
						ea_str = str(s.get('evlu_amt', s.get('evlt_amt', '0'))).replace(',', '')
						evlt_amt = int(float(ea_str))
					except: pass
					
					# [재계산] 현재가가 보정(0->평단가)되었거나, 평가금액이 0이면 직접 계산
					if evlt_amt == 0 or (cur_prc > 0 and abs(evlt_amt - (cur_prc * qty)) > evlt_amt * 0.1):
						# 기존 evlt_amt가 너무 이상하거나 0이면 재계산
						evlt_amt = int(cur_prc * qty)
					
					item['evlt_amt'] = evlt_amt
					
					# [Fix] 2. 평가손익 (pl_amt) - API 원본 우선 사용
					pl_amt = 0
					try:
						# API 필드: pl_amt 또는 evlu_pfls_amt
						pl_str = str(s.get('pl_amt', s.get('evlu_pfls_amt', '0'))).replace(',', '')
						pl_amt = int(float(pl_str))
					except: pass
					
					# UI 전달용 평균가
					item['pchs_avg_pric'] = int(avg_prc)

					# [재계산 로직 개선] 
					# API 원본 pl_amt가 0이고, 현재가가 정상적으로 있을 때만 재계산
					if pl_amt == 0 and cur_prc > 0 and pur_amt > 0:
						# 재계산: (현재가 - 평단가) * 수량 (이 방식이 가장 정확함)
						pl_amt = int((cur_prc - avg_prc) * qty)
					
					item['pl_amt'] = pl_amt
					
					# [Fix] 총 합계 누적
					total_eval_sum += evlt_amt
					total_pl_sum += pl_amt
					total_buy_sum += pur_amt
					
					# 3. 수익률 (pl_rt) - API 원본 우선 사용
					pl_rt = 0.0
					try:
						# API 필드: pl_rt 또는 pfit_rt
						rt_str = str(s.get('pl_rt', s.get('pfit_rt', '0'))).replace(',', '')
						pl_rt = float(rt_str)
					except: pass

					# API 수익률이 0이거나 사용자가 강제 재계산을 원할 경우 (현재가/평단가 기준)
					if (pl_rt == 0.0 or True) and avg_prc > 0 and cur_prc > 0:
						pl_rt = ((cur_prc - avg_prc) / avg_prc) * 100
					
					# [Safety] 현재가 0원(데이터 오류)이면 수익률도 0% 처리
					if cur_prc <= 0:
						pl_rt = 0.0
						
					item['pl_rt'] = f"{pl_rt:.2f}"
					
					# 보유 시간
					item['hold_time'] = "0분"
					if code in self.held_since:
						mn = int((time.time() - self.held_since[code]) / 60)
						item['hold_time'] = f"{mn}분"
					
					# [Sync] 팩터(Factor) 기반 단계 계산 로직 (수익률 기준)
					st_strategy = str(get_setting('single_stock_strategy', get_setting('strategy', 'WATER'))).upper()
					strategy_rate_val = float(get_setting('single_stock_rate', 1.5))
					s_cnt = int(float(get_setting('split_buy_cnt', 5))) # 분할 횟수
					
					# [Step Calc] DB 기록 기반 단계 판독 (사용자 요청: 매수 명령 횟수 = 단계)
					cur_st_mode = "REAL"
					try:
						if str(get_setting('use_mock_server', False)).lower() in ['1', 'true', 'on']: cur_st_mode = "MOCK"
						elif str(get_setting('is_paper_trading', False)).lower() in ['1', 'true', 'on']: cur_st_mode = "PAPER"
					except: pass
					
					db_step = get_watering_step_count_sync(code, cur_st_mode)
					
					# [UI Logic] 비중 기반 판독 보강
					f_ratio = pur_amt / alloc_per_stock if alloc_per_stock > 0 else 0
					
					# 1. DB 기록이 있으면 우선 신뢰
					computed_step = db_step
					
					# 2. 비중이 특정 단계를 명확히 넘었을 경우 (예: 1단계 비중 초과 시 2단계)
					# cumulative_ratios[0]은 1단계의 목표 비중임 (예: 25%)
					# 현재 비중이 이 값을 넘으면 실질적으로 2단계 매집이 시작된 것으로 간주
					if len(cumulative_ratios) > 0:
						if f_ratio > cumulative_ratios[0] * 0.95: # 5% 여유폭
							if computed_step < 2: computed_step = 2
						
						# 추가 단계 체크 (수열 기반)
						for i in range(1, len(cumulative_ratios)):
							if f_ratio > cumulative_ratios[i] * 0.95:
								if computed_step < i + 2: computed_step = i + 2

					# [절대 규칙] 1주면 무조건 1차 (비중 오차 방지)
					if qty <= 1:
						computed_step = 1
					elif computed_step == 0:
						computed_step = 1
						
					# [Robust Fix] 수량이 적은데 비중만 높은 경우(저가주 등) 강제 하향 조정
					if qty == 2 and computed_step > 2: computed_step = 2 
					elif qty == 3 and computed_step > 3: computed_step = 3

					display_step = computed_step if computed_step <= s_cnt else s_cnt
					
					# [UI Labeling]
					step_str = f"{computed_step}차"
					if computed_step >= s_cnt:
						step_str = f"{computed_step}차(MAX)"
					
					item['watering_step'] = step_str
					
					# [Debug] 엔진 로그 출력 (단계를 건너뛸 때)
					if computed_step > 1:
						logger.info(f"📊 [UI] {code}: {pl_rt:.1f}% -> {step_str}")
					
					# [UI Feedback] 매집 상태 (Time-Cut 여부)
					# 정밀도 상향 (90% -> 95%)
					if pur_amt < alloc_per_stock * 0.95:
						item['note'] = "매집 중 (TimeCut 보류)"
					else:
						item['note'] = "매집 완료 (감시 중)"
					
					status_holdings.append(item)
				except Exception as e:
					logger.error(f"Status Update Error for {s.get('stk_nm')}: {e}")

		# 최종 자산 update
		# [Fix] deposit 또는 total_eval_sum이 None일 경우를 위한 안전장치
		total_asset = int(deposit or 0) + int(total_eval_sum or 0)
		
		# [Asset Offset] 모의투자 계좌 기본값(3억)과 실제 시작 자산(5억) 차이 보정
		# [Fix] get_setting('asset_offset')이 None일 수 있으므로 integer 변환 필수
		asset_offset_raw = get_setting('asset_offset', 0)
		asset_offset = int(asset_offset_raw if asset_offset_raw is not None else 0)
		
		if asset_offset != 0:
			total_asset += asset_offset
			logger.debug(f"[Asset Offset] {asset_offset:,}원 적용 -> 보정 후 총자산: {total_asset:,}원")
		
		# API 모드 확인
		api_mode = get_current_api_mode() # "Mock" or "Real"
		
		# [안전장치] 자산 급락 체크
		if self.last_valid_total_asset > 0:
			if total_asset < self.last_valid_total_asset * 0.7:
				logger.warning(f"[GUI] 자산 급락 감지 ({self.last_valid_total_asset} -> {total_asset}) - 갱신 스킵")
				return time.time()
		self.last_valid_total_asset = total_asset

		# [Fix] 합산 방식을 holdings 리스크 기반으로 변경하여 데이터 불일치 완벽 차단
		final_eval = sum(h['evlt_amt'] for h in status_holdings)
		final_buy = sum(h['pur_amt'] for h in status_holdings)
		final_pl = sum(h['pl_amt'] for h in status_holdings)

		# JSON 구조 생성
		summ_dict = {
			"total_asset": deposit + final_eval,
			"total_buy": final_buy,
			"deposit": deposit,
			"total_pl": final_pl,
			"total_yield": (final_pl / final_buy * 100) if final_buy > 0 else 0,
			"bot_running": (not self.manual_stop) and self.chat_command.rt_search.connected,
			"initial_asset": self.chat_command.initial_asset or total_asset,
			"api_mode": api_mode,
			"is_paper": get_setting('is_paper_trading', True)
		}
		
		status_data = {
			"summary": summ_dict,
			"holdings": status_holdings
		}
		
		# [DB] 상태 저장 (status.json 대체)
		save_system_status(status_data)
		
		return time.time()

	def _optimize_stock_count_by_budget(self):
		"""
		[AI Smart Count]
		현재 예수금을 기준으로 '물타기를 끝까지 버틸 수 있는' 적정 종목 수를 역산하여 자동 설정합니다.
		오직 REAL(실전) 모드에서만 동작하며, 사용자 설정을 스마트하게 보정합니다.
		"""
		try:
		# 실전 모드 확인
			if get_setting('use_mock_server', False) or get_setting('is_paper_trading', False):
				# [Mock 모드 Safety] Mock 모드인데 종목 수가 1개면 테스트가 안되므로 5개로 복구
				current_target = int(float(str(get_setting('target_stock_count', 5))))
				if current_target <= 1:
					save_setting('target_stock_count', 5)
					logger.info("🧪 [Mock 모드 감지] 원활한 테스트를 위해 종목 수를 1개 -> 5개로 자동 확장합니다.")
				return

			# 1. 가용 현금 확인 (예수금)
			deposit = int(get_setting('deposit', 0))
			if deposit <= 0: return

			# 2. 현재 설정된 종목 당 투자 비중 (기본 70%)
			capital_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0
			total_investable = deposit * capital_ratio # 총 운용 가능 금액

			# 3. 1종목 완주(5회 물타기)에 필요한 예상 최소 비용
			# 가정: 1주가 약 2,000원인 저가주 기준 (너무 비싼 주식은 애초에 매수가 안 되므로)
			# 1차(1) + 2차(1) + 3차(2) + 4차(4) + 5차(8) = 총 16유닛
			UNIT_PRICE_EST = 2000 # 2천원 짜리 주식 기준
			TOTAL_UNITS = 1 + 1 + 2 + 4 + 8 # 16
			
			cost_per_stock_full_cycle = UNIT_PRICE_EST * TOTAL_UNITS # 한 종목당 약 32,000원 필요
			
			# 4. 역산: 몇 종목이나 버틸 수 있는가?
			optimal_count = int(total_investable // cost_per_stock_full_cycle)
			
			# [Safety] 최소 1개, 최대 10개 제한
			if optimal_count < 1: optimal_count = 1
			if optimal_count > 10: optimal_count = 10
			
			# 5. 현재 설정과 비교하여 다르면 자동 보정
			current_target = int(get_setting('target_stock_count', 5))
			
			if optimal_count != current_target:
				logger.info(f"💡 [AI 예산 최적화] 예수금({deposit:,}원) 기준 적정 종목 수 재산정: {current_target}개 -> {optimal_count}개")
				save_setting('target_stock_count', optimal_count)
				
				# 사용자 알림 (로그)
				self.chat_command.send_telegram_message(f"💰 [자금 최적화] 예수금({deposit:,}원)에 맞춰 운용 종목 수를 {optimal_count}개로 자동 조정했습니다.")
				# 시작 시점이 아닐 때만 음성 알림 (시작 시에는 가디언이 이미 보고함)
				if self.today_started:
					speak(f"자금 상황에 맞춰 운용 종목 수를 {optimal_count}개로 자동 보정하였습니다.")
			else:
				logger.info(f"✅ [예산 점검] 현재 예수금({deposit:,}원)으로 {current_target}개 종목 운용 가능함.")
				
		except Exception as e:
			logger.error(f"예산 최적화 계산 중 오류: {e}")

	async def run(self):
		"""메인 실행 루프"""
		self.loop = asyncio.get_running_loop()
		logger.info("="*50)
		logger.info("키움 자동매매 봇 시작")
		logger.info("="*50)
		logger.info("채팅 모니터링을 시작합니다...")
		
		# [System Log] API Mode Logging
		api_mode = get_current_api_mode()
		mode_kr = "가상 서버 (Mock)" if api_mode == "Mock" else "실제 키움 (Real)"
		
		# [Smart Count] 시작 시에도 예산 점검
		self._optimize_stock_count_by_budget()

		logger.info(f"[시스템] 현재 실행 모드: {mode_kr}")
		
		# [초기 토큰 발급] 봇 실행 시 바로 로그인을 시도합니다.
		if self.chat_command.token is None:
			logger.info("초기 토큰 발급 시도...")
			self.chat_command.get_token()

		# speak("라스트트레이드 시스템이 온라인 상태가 되었습니다. 자동 매매를 시작합니다.")

		# [System] 초기화
		reset_accumulation_global()
			
		# [자동 시작] 프로그램 실행 시 즉시 시작 (User requirement)
		logger.info("[Startup] 시스템 자동 시작...")
		await self.chat_command.start(force=True)
		self.today_started = True

		# [Startup] Generate initial report (Trading Logs & Assets)
		# 반드시 async loop 내에서 실행되어야 함
		try:
			logger.info("Generating initial startup report...")
			await self.chat_command.report(send_telegram=False)
		except Exception as e:
			logger.error(f"Failed to generate startup report: {e}")

			
		last_json_update = 0
		
		# 초기 모드 저장
		self.last_api_mode = get_current_api_mode()
		
		# 시스템 시작 메시지
		start_time = datetime.datetime.now().strftime('%H:%M:%S')
		logger.info(f"🚀 LASTTRADE 시스템 시작 [{start_time}] - 모드: {self.last_api_mode}")
		logger.info(f"🔍 [Debug] Mock Learning 초기화: 모드={self.last_api_mode}, last_mock_learn_time={self.last_mock_learn_time}, 현재시각={time.time()}")
		
		try:
			while self.keep_running:
				# [Heartbeat] 생존 신고
				self._send_heartbeat()

				# [Mode Change Check] API 모드 변경 감지 및 토큰 갱신
				current_api_mode = get_current_api_mode()
				if self.last_api_mode != current_api_mode:
					logger.warning(f"⚠️ API 모드 변경 감지: {self.last_api_mode} -> {current_api_mode}. 토큰을 재발급합니다.")
					
					# 키움 어댑터 내부 인스턴스 초기화
					from kiwoom_adapter import get_active_api
					get_active_api()
					
					# 토큰 재발급
					self.chat_command.token = None
					self.chat_command.get_token(force=True)
					self.last_api_mode = current_api_mode
					
					mode_text = "실전 매매" if current_api_mode == "Real" else "모의 투자"
					speak(f"경고. 매매 모드가 {mode_text}로 변경되었습니다. 시스템을 재배치합니다.")
					
					# [Fix] 자산 급락 감지 초기화 (모드 변경 시 자산 규모가 다르므로)
					self.last_valid_total_asset = 0
					
					# [Critical Fix] 모드 변경 시 내부 보유 목록 및 추적 데이터 완전 초기화
					self.held_since.clear()
					self.chat_command.rt_search.purchased_stocks.clear()
					reset_accumulation_global()
					
					# [Restart Fix] 기존의 낡은 연결/루프가 남아 '어리버리'하게 작동하는 것 방지
					# 엔진을 강제로 중지시키면, 다음 check_market_timing()에서 새로운 모드로 start()가 트리거됨
					# today_started를 False로 하여 새 모드에서의 시작 보고서도 다시 보내게 함
					logger.warning(f"🔄 [{current_api_mode}] 환경으로 재배치 중... 기존 엔진을 종료합니다.")
					await self.chat_command.stop(set_auto_start_false=False)
					self.today_started = False 
					
					logger.info("⚠️ API 모드 변경으로 인해 내부 데이터가 초기화되었으며, 곧 새로운 모드로 재시작됩니다.")
				
				# 채팅 메시지 확인
				message = await self.get_chat_updates()
				if message:
					await self.chat_command.process_command(message)
				
				# [Mock Mode Learning] 30분마다 자동 학습 (사용자 요청)
				# Debug: 현재 모드 확인
				if current_api_mode.upper() == "MOCK":
					time_diff = time.time() - self.last_mock_learn_time
					if time_diff > 1800:  # 30분 = 1800초
						logger.info("🧠 [Mock Learning] 30분이 경과하여 AI 자율 학습을 시작합니다...")
						try:
							import subprocess
							import sys
							subprocess.Popen([sys.executable, "learn_daily.py"])
							self.last_mock_learn_time = time.time()
							logger.info("🧠 [Mock Learning] 학습 프로세스(learn_daily.py)가 백그라운드에서 시작되었습니다.")
						except Exception as e:
							logger.error(f"학습 프로세스 실행 실패: {e}")
				
				# 장 시작/종료 시간 확인
				await self.check_market_timing()

				
				# [Watchdog] 실시간 검색 엔진 연결 상태 감시 및 복구
				# 장 시간이고, 자동 시작 상태인데 연결이 끊겨있거나 데이터가 안 온다면 재시작
				if self.today_started and MarketHour.is_market_buy_time() and not self.manual_stop:
					rt = self.chat_command.rt_search
					# 1. 아예 연결이 끊긴 경우
					# 2. 연결은 되어있으나 30초 이상 데이터(Recv)가 없는 경우 (좀비 연결)
					#    [Fix] Mock 모드에서는 데이터 수신이 불규칙하므로 좀비 체크 타임아웃을 5분으로 늘림
					zombie_timeout = 300 if get_current_api_mode() == "Mock" else 30
					is_zombie = rt.connected and (time.time() - getattr(rt, 'last_msg_time', 0) > zombie_timeout)
					
					if not rt.connected or is_zombie:
						if is_zombie:
							logger.warn(f"⚠️ [Watchdog] 좀비 연결 감지 (마지막 수신: {time.time() - rt.last_msg_time:.1f}초 전). 재연결 시도!")
						else:
							logger.warn("⚠️ [Watchdog] 검색 엔진 연결 끊김 감지! 재연결을 시도합니다.")
						
						# 확실한 재시작을 위해 stop 호출 후 start(force=True)
						await self.chat_command.stop(set_auto_start_false=False)
						await asyncio.sleep(2)
						await self.chat_command.start(force=True) # force 플래그 추가
						
						if not rt.connected:
							logger.error("❌ [Watchdog] 검색 엔진 재연결 실패. 다음 루프에서 재시도합니다.")
				
				# [Token Auto-Renewal] 토큰 자동 갱신 (4시간마다 또는 날짜 변경 시)
				try:
					current_time = time.time()
					current_date = datetime.datetime.now().date()
					token_age = current_time - self.last_token_time
					
					# 토큰 갱신 조건: 4시간(14400초) 경과 또는 날짜 변경
					if token_age > 14400 or (self.last_token_date and current_date > self.last_token_date):
						logger.info(f"토큰 갱신 필요 (경과 시간: {token_age/3600:.1f}시간, 날짜 변경: {current_date != self.last_token_date})")
						self.chat_command.get_token(force=True)
						if self.chat_command.token:
							self.last_token_time = current_time
							self.last_token_date = current_date
							logger.info("✅ 토큰 갱신 완료")
				except Exception as e:
					logger.error(f"토큰 갱신 실패: {e}")

				# [Throttling] 루프 속도 조절 (CPU 및 DB 지연 방지) - 반응성 위해 대폭 단축
				await asyncio.sleep(0.05)

				# [Web Dashboard] 웹 대시보드에서 명령어 확인
				# logger.debug("Checking web commands...")
				await self.check_web_command()

				
				# [Pause Check] 일시정지 상태 확인 (manual_stop 플래그 우선)
				if self.manual_stop:
					self._send_heartbeat()
					await asyncio.sleep(1)
					continue
				
				from database_helpers import get_bot_running
				if not get_bot_running():
					self._send_heartbeat()
					await asyncio.sleep(1)
					continue

				# [Math] 분봉 캔들 및 대응 데이터(Response) 업데이트
				await candle_manager.process_minute_candles()
				await response_manager.update_metrics(self.chat_command.rt_search.current_prices)

				
				# [추가] 보유 종목 물타기/관리 및 모니터링 루프 (Dynamic Rate Limit)
				# [Fix] 실전/모의투자 시 호출 제한 방지를 위해 간격 확대 (4.0 -> 8.0) -> [Revert] TS 반응성 위해 0.2초로 단축
				# (보유 종목이 적을 때는 API 제한에 걸리지 않으므로 빠른 대응 우선)
				limit_interval = 0.2
				if time.time() - last_json_update > limit_interval:

					try:
						# [Time-Cut] 매도 로직 실행 전에 held_since 정보를 ChatCommand에 전달
						# (매도 로직에서 시간컷 체크를 위해 필요)
						self.chat_command.held_since = self.held_since
						
						# [Seq 1] 매도 로직 (순차 실행)
						# 매도 체크를 가장 먼저 수행하여 현금 확보 및 포트폴리오 정리
						# [Refactoring] Helper Methods 호출
						loop = asyncio.get_running_loop()
						
						# 1. 데이터 업데이트 (최우선 실행)
						self._send_heartbeat() # 긴 작업 시작 전 신호
						current_stocks, current_balance, balance_data = await self._update_market_data(loop)
						self._send_heartbeat() # 작업 직후 신호
						
						# [Fix] 데이터가 정상적으로 전달되지 않았을 경우 이번 루프 즉시 패스 (지연 방지)
						if current_stocks is None or balance_data is None:
							await asyncio.sleep(0.1)
							continue
							
						deposit_amt = balance_data.get('deposit', 0)
						
						# [New] 미체결 데이터 조회 (chk_n_buy/chk_n_sell 중복 호출 방지)
						from kiwoom_adapter import get_api
						api = get_api()
						out_orders = await loop.run_in_executor(None, api.get_outstanding_orders, self.chat_command.token)

						# 2. 매도 로직 실행 (상태 데이터 주입)
						await self.chat_command.run_sell_logic(current_stocks, deposit_amt, out_orders)
						
						# 3. 안전 감시 (상태 데이터 주입)
						await self.chat_command.monitor_safety(deposit_amt, current_stocks)

						# 4. 로직 실행 (유효 데이터 존재 시)
						if current_stocks is not None:
							# [Sync] 내부 추적 데이터(매입금액) 동기화
							# sync_accumulated_amounts(current_stocks)
							
							# [Sync] 보유 시간 동기화 (재시작 시 타이머 자동 시작)
							for s in current_stocks:
								code = normalize_stock_code(s.get('stk_cd', ''))
								if code and code not in self.held_since:
									self.held_since[code] = time.time()
									logger.info(f"[Sync] {code} 보유 시간 추적 시작 (기존 보유 종목)")
							
							# 동기화
							self.chat_command.rt_search.update_held_stocks(current_stocks)
							await self._sync_holdings(current_stocks, balance_data)
							
							# [Fix] 위(Line 696)에서 이미 조회했으므로 기존 out_orders 재사용 (호출 제한 방지)
							# out_orders = await loop.run_in_executor(None, api.get_outstanding_orders, self.chat_command.token)
							
							# 물타기 (장중 매수 시간)
							if MarketHour.is_market_buy_time():
								self._send_heartbeat() # 매수 로직 진입 전
								await self._process_watering_logic(current_stocks, balance_data, out_orders)
								self._send_heartbeat() # 매수 로직 완료 후
								
							# GUI 상태 업데이트
							last_json_update = await self._update_status_json(current_stocks, balance_data, current_balance)
							
							# [Display] 보유 시간 (1분 간격)
							if int(time.time()) % 60 < 2 and self.held_since:
								logger.info(f"[보유시간 현황] {len(self.held_since)}개 종목 추적 중")

					except Exception as e:
						import traceback
						logger.error(f"[MainLoop] 주기적 루프 오류:\n{traceback.format_exc()}")
						await asyncio.sleep(5) # 오류 시 대기
						
				# [AI Smart Count] 자동 보정 비활성화 (사용자 요청: 5종목 고정)
				# if not get_setting('use_mock_server', False):
				# 	self._optimize_stock_count_by_budget()

				# [Start] AI 추천기 시작 (상시 체크)
				if not self.ai_recommender.running:
					self.ai_recommender.start()

				# 1분 통계 기록
				now = datetime.datetime.now()
				if now.second == 0:
					try:
						# 자산 기록 (간소화)
						if self.last_valid_total_asset > 0:
							profit = 0
							if self.chat_command.initial_asset:
								profit = self.last_valid_total_asset - self.chat_command.initial_asset
							await log_asset_history(self.last_valid_total_asset, profit)
					except Exception as e: pass
					await asyncio.sleep(1)


					
				# [Auto-Cancel] 미체결 매수 주문 자동 취소 (매도는 자동 취소 제외)
				# [Throttle] 과도한 API 호출 방지 (20초에 한 번만 실행)
				if time.time() - self.last_autocancel_time > 20: 
					self.last_autocancel_time = time.time()
					try:
						from config import outstanding_orders
						from kiwoom_adapter import get_api
						
						token = self.chat_command.token
						if token:
							api = get_api()
							try:
								real_outstanding = api.get_outstanding_orders(token)
								
								if real_outstanding is not None: # None(에러)이 아닐 때만 처리
									# 2. 미체결 주문 취소 처리
									for order in real_outstanding:
										try:
											ord_no = order.get('ord_no', order.get('ORD_NO', ''))
											stk_cd = order.get('stk_cd', order.get('STK_CD', ''))
											ord_qty = order.get('ord_qty', order.get('ORD_QTY', '0'))
											ord_tp = order.get('ord_tp_nm', order.get('ORD_TP_NM', ''))
											
											if '매수' in ord_tp and ord_no and stk_cd:
												order_timestamp = 0
												for ts, info in outstanding_orders.items():
													res = info.get('result', {})
													if str(res.get('ORD_NO', res.get('ord_no', ''))) == str(ord_no):
														order_timestamp = ts
														break
												
												if order_timestamp > 0 and (time.time() - order_timestamp < 120):
													continue 
													
												logger.info(f"[AutoCancel] 미체결 매수 주문 취소 시도: {stk_cd} {ord_qty}주 (주문번호: {ord_no})")
												cancel_code, cancel_msg = api.cancel_stock(stk_cd, ord_qty, ord_no, token)
												
												if str(cancel_code) in ['0', 'SUCCESS']:
													logger.info(f"[AutoCancel] ✅ 매수 취소 성공: {stk_cd}")
												else:
													logger.warning(f"[AutoCancel] ❌ 매수 취소 실패: {cancel_msg}")
										except Exception as e:
											logger.error(f"[AutoCancel] 개별 주문 취소 오류: {e}")
							except Exception as e:
								logger.error(f"[AutoCancel] 미체결 조회 실패: {e}")
						
						# 3. 내부 추적 데이터 정리 (2분 이상 경과한 항목 제거)
						current_time = time.time()
						to_remove = [k for k, v in outstanding_orders.items() if current_time - k > 120]
						for k in to_remove:
							if k in outstanding_orders:
								del outstanding_orders[k]
								
					except Exception as e:
						logger.error(f"[AutoCancel] 로직 오류: {e}")

				# [AI Queue Processing] 큐에 쌓인 AI 추천 처리
				try:
					import config
					while config.ai_recommendation_queue:
						item = config.ai_recommendation_queue.pop(0)
						code = item['code']
						
						# 중복 매수 방지 (오늘 이미 시도했으면 스킵 - global set 활용)
						# 하지만 '무조건 매수' 모드라면 이것도 무시 가능
						
						logger.info(f"🤖 [Queue Pop] AI 추천 매수 실행: {code} (점수:{item['ai_score']})")
						
						if self.chat_command.token:
							await self._async_chk_n_buy(
								code, 
								self.chat_command.token, 
								item['source'], 
								item['ai_score'], 
								item['ai_reason']
							)
						else:
							logger.warning("⚠️ 토큰 미발급으로 매수 보류 (Queue에서 소멸)")
				except Exception as e:
					logger.error(f"AI Queue 처리 중 오류: {e}")

				# 0.1초 대기 (응답성 향상)
				await asyncio.sleep(0.1)
				
		except KeyboardInterrupt:
			logger.info("\n사용자에 의해 프로그램을 종료합니다...")
			self.keep_running = False
			await self.chat_command.stop(False)
		except Exception as e:
			logger.error(f"메인 루프에서 예상치 못한 오류 발생: {e}", exc_info=True)
			self.keep_running = False
			await self.chat_command.stop(False)

async def main():
	import os
	import ctypes
	if os.name == 'nt':
		ctypes.windll.kernel32.SetConsoleTitleW("🤖 Kiwoom Trading Engine (Main Bot)")
	
	script_dir = os.path.dirname(os.path.abspath(__file__))
	
	# 설정 데이터 검증 (DB 기반)
	from database_helpers import get_all_settings
	settings = get_all_settings()
	
	is_valid, errors = SettingsValidator.validate_all_settings(settings)
	if not is_valid:
		logger.error("DB 설정 값 검증 실패:")
		for error in errors:
			logger.error(f"  - {error}")
		logger.error("데이터베이스 설정을 확인해 주세요.")
		# 치명적인 오류가 아니라면 일단 실행은 하되, 로그로 알림
		# logger.error("프로그램을 종료합니다.")
		# return
	
	logger.info("기본 설정 검증 완료 (DB 기반)")
	
	# 데이터베이스 초기화
	await init_db()
	
	# [New] 대시보드 서버 시작
	# [New] 대시보드 서버 시작 (별도 프로세스로 분리)
	# -> start.py 런처에서 통합 실행하므로 여기서는 제외함 (중복 실행 방지)
	# try:
	# 	import sys
	# 	import subprocess
	# 	logger.info("Starting Dashboard Server (subprocess)...")
	# 	dash_script = os.path.join(script_dir, 'dashboard.py')
	# 	# 로그 파일에 출력 리다이렉트 (디버깅용)
	# 	log_path = os.path.join(script_dir, 'dashboard.log')
	# 	log_fd = open(log_path, 'w', encoding='utf-8')
	# 	# Popen으로 실행 (독립 프로세스)
	# 	subprocess.Popen([sys.executable, dash_script], stdout=log_fd, stderr=log_fd)
	# except Exception as e:
	# 	logger.error(f"대시보드 시작 실패: {e}")

	# 중복 실행 방지
	lockfile = os.path.join(script_dir, 'main.lock')
	
	try:
		with SingleInstance(lockfile):
			app = MainApp()
			await app.run()
	except Exception as e:
		import traceback
		logger.error(f"메인 프로세스 오류:\n{traceback.format_exc()}")
		# [Debug] 오류 발생 시 창이 바로 닫히지 않도록 대기 (start.py에서 모니터링 중)
		await asyncio.sleep(10)
	finally:
		# 종료 시 정리
		logger.info("프로그램이 완전히 종료되었습니다.")

if __name__ == '__main__':
	import sys
	try:
		asyncio.run(main())
		# 정상 종료
		sys.exit(0)
	except KeyboardInterrupt:
		logger.info("사용자 요청으로 프로그램을 종료합니다.")
		sys.exit(0)  # Ctrl+C도 정상 종료로 간주
	except Exception as e:
		logger.error(f"치명적 오류로 프로그램 종료: {e}")
		sys.exit(1)  # 비정상 종료
