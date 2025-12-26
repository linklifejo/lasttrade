import asyncio
import aiohttp
import datetime
import os
import json
import time
from config import telegram_token
from chat_command import ChatCommand
from single_instance import SingleInstance
from logger import logger
from settings_validator import SettingsValidator
from utils import normalize_stock_code
from file_utils import safe_write_json, safe_read_json

from get_setting import get_setting
from market_hour import MarketHour
from database import init_db, log_asset_history, log_price_history
from database_helpers import save_system_status, get_pending_web_command, mark_web_command_completed
# from dashboard import run_dashboard_server # Subprocess로 실행됨
# [Mock Server Integration] Use kiwoom_adapter for automatic Real/Mock API switching
from kiwoom_adapter import fn_kt00004 as get_my_stocks, get_account_data, get_total_eval_amt, get_current_api_mode
from kiwoom_adapter import fn_kt00001 as get_balance
from check_n_buy import chk_n_buy, reset_accumulation_global
from candle_manager import candle_manager

class MainApp:
	def __init__(self):
		self.chat_command = ChatCommand()
		

			
		self.market_open_notified = False
		self.last_update_id = 0
		self.telegram_url = f"https://api.telegram.org/bot{telegram_token}/getUpdates"
		self.keep_running = True
		self.today_started = False  # 오늘 start가 실행되었는지 추적
		self.today_stopped = False  # 오늘 stop이 실행되었는지 추적
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
		
		# [Persistent Held Time] - DB 기반
		self.load_held_times()
		
		# [Time-Cut Fix] rt_search에 held_since 참조 전달 (매수 즉시 타이머 등록 가능)
		self.chat_command.rt_search.held_since_ref = self.held_since
		
	def load_held_times(self):
		"""DB에서 보유 시간 로드"""
		try:
			from database_helpers import get_all_held_times
			self.held_since = get_all_held_times()
			logger.info(f"보유 시간 DB 로드 완료: {len(self.held_since)}개 종목")
		except Exception as e:
			logger.error(f"보유 시간 DB 로드 실패: {e}")
			self.held_since = {}

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
		"""장 시작/종료 시간을 확인하고 자동 실행합니다."""
		auto_start = get_setting('auto_start', False)
		today = datetime.datetime.now().date()
		
		# 새로운 날이 되면 플래그 리셋
		if self.last_check_date != today:
			self.today_started = False
			self.today_stopped = False
			self.last_check_date = today
		
		# 1. 자동 시작 처리
		if auto_start and not self.manual_stop:
			# 장중인데 아직 연결 안됨 -> 시작 시도
			if MarketHour.is_market_open_time():
				if not self.chat_command.rt_search.connected:
					logger.info(f"장중 자동 시작 실행 (연결 없음) - start 명령을 실행합니다.")
					await self.chat_command.start()
					self.today_started = True
			
			# 장전인데 아직 플래그가 안 켜졌으면 (로그 출력용)
			elif not self.today_started:
				logger.info(f"자동 시작 대기 중 - 장 시작 시 자동으로 연결됩니다.")
				self.today_started = True # 메시지 중복 방지용
		
		# 2. 장 종료 처리
		if MarketHour.is_market_end_time() and not self.today_stopped:
			logger.info(f"장 종료 시간({MarketHour.MARKET_END_HOUR:02d}:{MarketHour.MARKET_END_MINUTE:02d})입니다. 자동으로 stop 명령을 실행합니다.")
			await self.chat_command.stop(False)  # auto_start를 false로 설정하지 않음
			logger.info("자동으로 계좌평가 보고서를 발송합니다.")
			await self.chat_command.report()  # 장 종료 시 report도 자동 발송
			self.today_stopped = True  # 오늘 stop 실행 완료 표시

	async def check_web_command(self):
		"""웹 대시보드에서 보낸 명령을 확인하고 처리합니다. (DB 기반)"""
		try:
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
					
					await self.chat_command.rt_search.start(self.chat_command.token)
					self.manual_stop = False # 수동 일시정지 해제
					
					# 누적 매수 금액 리셋
					from check_n_buy import reset_accumulation_global
					reset_accumulation_global()
					
					# [Immediate Refresh] 즉시 데이터 갱신하여 UI 반영
					logger.info("🔄 [System] 데이터 즉시 갱신 중...")
					loop = asyncio.get_running_loop()
					stocks, bal, bal_data = await self._update_market_data(loop)
					if stocks is not None:
						await self._update_status_json(stocks, bal_data, bal)
					
					logger.info("✅ [System] 재초기화 및 데이터 동기화 완료.")
					
				elif command == 'report':
					# 웹에서 리포트 요청 시 텔레그램 발송 없이 JSON만 업데이트
					await self.chat_command.report(send_telegram=False)
				else:
					# 시작/종료 명령 시 즉시 로그 출력
					if command == 'stop':
						self.manual_stop = True
					elif command == 'start':
						self.manual_stop = False
						
					logger.info(f"⚙️ 명령 실행 중: {command}...")
					await self.chat_command.process_command(command)
					logger.info(f"✅ 명령 실행 완료: {command}")
					
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
			if acnt_data:
				current_stocks, acnt_summary = acnt_data
			else:
				current_stocks, acnt_summary = [], {}
				
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
			use_mock = get_setting('use_mock_server', True)
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
				for code in list(self.held_since.keys()):
					if code not in current_codes:
						del self.held_since[code]
						changed = True
				if changed: self.save_held_times()

	async def _process_watering_logic(self, current_stocks, balance_data, outstanding_orders=None):
		"""물타기/불타기 조건 체크 로직 (Refactoring Helper)"""
		for stock in current_stocks:
			code = normalize_stock_code(stock.get('stk_cd', ''))
			if code:
				await asyncio.get_event_loop().run_in_executor(
					None, chk_n_buy, code, self.chat_command.token, current_stocks, balance_data, self.held_since, outstanding_orders
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
		if balance_data: deposit = int(balance_data['deposit'])
		elif current_balance: 
			try: deposit = int(current_balance[2])
			except: pass

		total_eval_sum = 0
		total_pl_sum = 0
		total_buy_sum = 0 # 실매입금 합계
		status_holdings = []

		# 설정 로드
		target_cnt = float(get_setting('target_stock_count', 1)) 
		if target_cnt < 1: target_cnt = 1
		split_cnt = int(float(get_setting('split_buy_cnt', 5)))
		
		# 분할 매수 비율 계산 (시각화용)
		weights = []
		for i in range(split_cnt):
			if i < 2: weights.append(1)
			else: weights.append(weights[-1] * 2)
		total_weight = sum(weights)
		cumulative_ratios = []
		curr_s = 0
		for w in weights:
			curr_s += w
			cumulative_ratios.append(curr_s / total_weight)
			
		# 추정 자산 총액
		temp_eval_sum = 0
		if current_stocks:
			for s in current_stocks:
				try:
					val = int(float(str(s.get('evlu_amt', '0')).replace(',','')))
					if val == 0: 
						prc = int(float(str(s.get('cur_prc', '0')).replace(',','')))
						qty = int(float(str(s.get('rmnd_qty', '0')).replace(',','')))
						val = prc * qty
					temp_eval_sum += val
				except: pass
		
		total_asset_est = deposit + temp_eval_sum

		# 실제 매수 로직과 동일하게 배정 금액 계산 (UI 표시용)
		capital_ratio = float(get_setting('trading_capital_ratio', 80)) / 100.0
		if int(target_cnt) == 1:
			alloc_per_stock = total_asset_est * 0.98
		else:
			alloc_per_stock = (total_asset_est * capital_ratio) / target_cnt
		
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
					
					# 평가손익 (pl_amt)
					pl_amt = 0
					try:
						pl_str = str(s.get('pl_amt', s.get('evlu_pfls_amt', '0'))).replace(',', '')
						pl_amt = int(float(pl_str))
					except: pass
					
					# [재계산] 평가손익 재계산 (현재가 보정 반영)
					# API 값이 신뢰성이 떨어지므로 직접 계산이 안전함
					if pur_amt > 0:
						pl_amt = evlt_amt - pur_amt
					item['pl_amt'] = pl_amt
					
					# [Fix] 총 합계 누적 (중복 합산 방지를 위해 여기서 한 번만 수행)
					total_eval_sum += evlt_amt
					total_pl_sum += pl_amt
					total_buy_sum += pur_amt
					
					# 수익률 (pl_rt)
					pl_rt = 0.0
					if pur_amt > 0:
						pl_rt = ((evlt_amt - pur_amt) / pur_amt) * 100
					
					# [Safety] 수익률이 -90% 밑이면 데이터 오류 가능성 높음 -> 0% 처리
					if pl_rt < -90.0:
						pl_rt = 0.0
						
					item['pl_rt'] = f"{pl_rt:.2f}"
					
					# 보유 시간
					item['hold_time'] = "0분"
					if code in self.held_since:
						mn = int((time.time() - self.held_since[code]) / 60)
						item['hold_time'] = f"{mn}분"
					
					# 단계(Step) 계산 로직 개선 (1단계 90% 이상 채워지면 2차로 표시)
					ratio = pur_amt / alloc_per_stock if alloc_per_stock > 0 else 0
					step_idx = 0
					for i, th in enumerate(cumulative_ratios):
						if ratio >= (th * 0.90): 
							step_idx = i + 1
						else: 
							break
					
					# [UI Labeling]
					if step_idx == 0:
						step_str = "1차(진입중)"
					elif step_idx == 1:
						# 1차 물량은 다 채웠고 2차 물량 채우는 중
						step_str = "1차(완료)"
					else:
						# [Fix] 전략 명칭에 맞는 정확한 용어 표시
						st_mode = str(get_setting('single_stock_strategy', get_setting('strategy', 'WATER'))).upper()
						mode_str = "물타기" if 'WATER' in st_mode else "불타기"
						
						# step_idx=2이면 '물타기 2차'
						step_str = f"{mode_str} {step_idx}차"
						if step_idx >= split_cnt: step_str += "(MAX)"
					
					item['watering_step'] = step_str
					
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
		total_asset = deposit + total_eval_sum
		
		# [Asset Offset] 모의투자 계좌 기본값(3억)과 실제 시작 자산(5억) 차이 보정
		asset_offset = int(get_setting('asset_offset', 0))
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
			"bot_running": self.chat_command.rt_search.connected,
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

	async def run(self):
		"""메인 실행 루프"""
		logger.info("="*50)
		logger.info("키움 자동매매 봇 시작")
		logger.info("="*50)
		logger.info("채팅 모니터링을 시작합니다...")
		
		# [System Log] API Mode Logging
		api_mode = get_current_api_mode()
		mode_kr = "가상 서버 (Mock)" if api_mode == "Mock" else "실제 키움 (Real)"
		logger.info(f"[시스템] 현재 실행 모드: {mode_kr}")
		
		# [초기 토큰 발급] 봇 실행 시 바로 로그인을 시도합니다.
		if self.chat_command.token is None:
			logger.info("초기 토큰 발급 시도...")
			self.chat_command.get_token()

		# [System] 초기화
		reset_accumulation_global()
			
		# [자동 시작] 프로그램 실행 시 즉시 시작 (User requirement)
		logger.info("[Startup] 시스템 자동 시작...")
		await self.chat_command.start()
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
		
		try:
			while self.keep_running:
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
					
					# [Fix] 자산 급락 감지 초기화 (모드 변경 시 자산 규모가 다르므로)
					self.last_valid_total_asset = 0
					
					# [Critical Fix] 모드 변경 시 내부 보유 목록 및 추적 데이터 완전 초기화
					self.held_since.clear()
					self.chat_command.rt_search.purchased_stocks.clear()
					reset_accumulation_global()
					logger.info("⚠️ API 모드 변경으로 인해 내부 보유 목록 및 추적 데이터를 초기화했습니다.")
				
				# 채팅 메시지 확인
				message = await self.get_chat_updates()
				if message:
					await self.chat_command.process_command(message)
				
				# 장 시작/종료 시간 확인
				await self.check_market_timing()
				
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
				
				# [Web Dashboard] 웹 대시보드에서 명령어 확인 (2초마다)
				await self.check_web_command()

				# [Candle] 분봉 생성 프로세스 실행
				await candle_manager.process_minute_candles()

				
				# [추가] 보유 종목 물타기/관리 및 모니터링 루프 (Dynamic Rate Limit)
				# [Fix] 실전/모의투자 시 호출 제한 방지를 위해 간격 확대 (4.0 -> 8.0)
				limit_interval = 1.0 if current_api_mode == "Mock" else 8.0
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
						current_stocks, current_balance, balance_data = await self._update_market_data(loop)
						
						# [Fix] 데이터가 정상적으로 전달되지 않았을 경우 이번 루프 스킵
						if current_stocks is None or balance_data is None:
							await asyncio.sleep(2)
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
								await self._process_watering_logic(current_stocks, balance_data, out_orders)
							
							# GUI 상태 업데이트
							last_json_update = await self._update_status_json(current_stocks, balance_data, current_balance)
							
							# [Display] 보유 시간 (1분 간격)
							if int(time.time()) % 60 < 2 and self.held_since:
								logger.info(f"[보유시간 현황] {len(self.held_since)}개 종목 추적 중")

					except Exception as e:
						logger.error(f"[MainLoop] 주기적 루프 오류: {e}")
						
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
		logger.error(f"메인 프로세스 오류: {e}")
	finally:
		# 종료 시 정리
		logger.info("프로그램이 완전히 종료되었습니다.")

if __name__ == '__main__':
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		pass
