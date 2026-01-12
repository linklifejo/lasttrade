import asyncio 
import websockets
import json
import time
from config import socket_url
from check_n_buy import chk_n_buy, reset_accumulation
from get_setting import get_setting
# [Mock Server Integration] Use kiwoom_adapter for automatic Real/Mock API switching
from kiwoom_adapter import fn_au10001 as get_token
from kiwoom_adapter import fn_kt00004 as get_my_stocks
from logger import logger

# chk_n_buy를 비동기로 실행하기 위한 wrapper 함수
async def async_chk_n_buy(stock_code, token):
	"""동기 함수인 chk_n_buy를 비동기로 실행하는 wrapper"""
	await asyncio.get_event_loop().run_in_executor(
		None, chk_n_buy, stock_code, token
	)


class RealTimeSearch:
	def __init__(self, on_connection_closed=None):
		self.socket_url = socket_url + '/api/dostk/websocket'
		self.websocket = None
		self.connected = False
		self.keep_running = True
		self.receive_task = None
		self.on_connection_closed = on_connection_closed  # 연결 종료 시 호출될 콜백 함수
		self.token = None  # 토큰 저장
		self.buying_stocks = set()  # 매수 진행 중인 종목 코드 추적 (중복 매수 방지)
		self.purchased_stocks = set() # 매수 완료/보유 중인 종목 코드 (매도 후 재매수 방지 등)
		self.buy_last_time = {}  # 종목별 마지막 매수 시도 시간 {code: timestamp}
		self.buy_lock = asyncio.Lock() # 매수 실행 동기화를 위한 락 (동시 체결 방지)
		self.recv_lock = asyncio.Lock() # WebSocket recv 동기화 락 (ConcurrencyError 방지)
		self.target_cnt_cache = None # [추가] 목표 종목 수 캐싱 (파일 읽기 경합 방지)
		self.candidate_queue = {} # [추가] 매수 대기열 {code: rate} (Priority Queue)
		self.recently_sold = {}        # [New] 최근 매도된 종목 (code: timestamp) - Ghost Stock 방지
		self.sold_time_log = {}        # [Fix] Legacy attribute for backward compatibility
		self.is_processing_candidates = False # [Priority] 후보군 처리 중 플래그
		self.current_prices = {} # [Cache] 실시간 현재가 캐시 {code: price}
		self.refresh_task = None # [New] 자동 갱신 태스크
		self.held_since_ref = None # [Time-Cut Fix] bot.py의 held_since 참조 (즉시 타이머 등록용)
		self.time_cut_cooldown = {} # [Time-Cut Fix] Time-Cut 매도 후 재매수 방지 {code: timestamp}
		self.pending_orders = {} # [New] 체결 확인 대기 목록 {code: timestamp}
		self.response_manager = None # [Math] 대응 데이터 추적기
		self.last_msg_time = time.time()  # [Watchdog Fix] 마지막 수신 시간 초기화
		
		# [동시성 제어] 후보군 처리 프로세스 락 (중복 매수 방지)
		self.candidates_lock = asyncio.Lock()
		self.processing_tasks = [] # [LifeCycle] 현재 실행 중인 매수 프로세스 트래킹

	def register_sold_stock(self, code):
		"""매도 완료된 종목을 등록하여, API 지연으로 인한 재진입(Ghost Check)을 방지합니다."""
		self.recently_sold[code] = time.time()
		logger.info(f"[Sold Register] {code} 매도 처리 등록 (Ghost 방지 시작)")

	async def register_stocks_realtime(self, codes):
		"""보유 종목(또는 특정 종목)을 서버에 실시간 시세 등록(SetRealReg) 요청합니다."""
		if not self.connected or not self.websocket:
			return
		
		if not codes:
			logger.info("📡 [SetRealReg] 등록할 종목 코드가 비어 있습니다.")
			return

		# 종목 코드가 리스트나 집합이면 세미콜론(;)으로 연결
		if isinstance(codes, (list, set)):
			codes_str = ";".join([str(c).replace('A', '') for c in codes])
		else:
			codes_str = str(codes).replace('A', '')

		param = {
			'trnm': 'REALREG', # 많은 Kiwoom Bridge에서 사용하는 SetRealReg 맵핑명
			'codes': codes_str
		}
		
		try:
			await self.send_message(message=param)
			logger.info(f"📡 [SetRealReg] 보유 종목 실시간 등록 요청 전송: {codes_str}")
		except Exception as e:
			logger.error(f"[SetRealReg] 요청 중 오류 발생: {e}")

	async def connect(self, token):
		"""WebSocket 서버에 연결합니다."""
		try:
			self.token = token  # 토큰 저장
			logger.info(f"🌐 [RT_SEARCH] connect() 시도 중... URL: {self.socket_url}")
			self.websocket = await websockets.connect(self.socket_url)
			self.connected = True
			logger.info("✅ [RT_SEARCH] WebSocket 연결 성공")

			# 로그인 패킷
			param = {
				'trnm': 'LOGIN',
				'token': token
			}

			logger.info('실시간 시세 서버로 로그인 패킷을 전송합니다.')
			# 웹소켓 연결 시 로그인 정보 전달
			await self.send_message(message=param)

		except Exception as e:
			logger.error(f'Connection error: {e}')
			self.connected = False
			self.websocket = None

	async def send_message(self, message, token=None):
		"""서버에 메시지를 보냅니다. 연결이 없다면 자동으로 연결합니다."""
		if not self.connected:
			if token:
				await self.connect(token)  # 연결이 끊어졌다면 재연결
		if self.connected and self.websocket:
			# message가 문자열이 아니면 JSON으로 직렬화
			if not isinstance(message, str):
				message = json.dumps(message)

			await self.websocket.send(message)
			logger.debug(f'Message sent: {message}')

	async def receive_messages(self):
		"""서버에서 오는 메시지를 수신하여 출력합니다."""
		logger.info("🚀 [RT_SEARCH] 메시지 수신 루프 시작")
		while self.keep_running and self.connected and self.websocket:
			raw_message = None
			try:
				# 서버로부터 수신한 메시지를 받음 (Lock으로 동시 접근 방지)
				async with self.recv_lock:
					raw_message = await self.websocket.recv()
				# JSON 형식으로 파싱
				if raw_message:
					print(f"DEBUG: WebSocket Msg Received: {raw_message[:100]}...")
					response = json.loads(raw_message)
				self.last_msg_time = time.time()
				
				# [Debug] 서버 수신 데이터 확인
				tr_code = response.get('trnm')
				if tr_code not in ['PING', 'PONG']:
					# 로그 과다 방지를 위해 너무 긴 데이터는 앞부분만 출력
					msg_preview = str(response)
					if len(msg_preview) > 300: msg_preview = msg_preview[:300] + "..."
					logger.info(f"📩 [Recv] {tr_code}: {msg_preview}")

				# 메시지 유형이 LOGIN일 경우 로그인 시도 결과 체크
				if response.get('trnm') == 'LOGIN':
					if response.get('return_code') != 0:
						logger.error(f"로그인 실패하였습니다. : {response.get('return_msg')}")
						await self.disconnect()
					else:
						logger.info('로그인 성공하였습니다.')
						logger.info('조건검색 목록조회 패킷을 전송합니다.')
						# 로그인 패킷
						param = {
							'trnm': 'CNSRLST'
						}
						await self.send_message(message=param)

				elif response.get('trnm') == 'PING':
					logger.debug(f'PING 메시지 수신: {response}')
					await self.send_message(response)

				# [Core Fix] 조건검색 목록(CNSRLST) 수신 시 -> 실시간 등록(CNSRREQ) 자동 수행
				elif response.get('trnm') == 'CNSRLST':
					logger.info(f"📋 조건검색 목록 수신: {len(response.get('data', []))}개")
					
					# 설정된 타겟 인덱스 (기본 0번)
					target_idx = 0
					try:
						# from get_setting (이미 상단 import됨)
						target_str = get_setting('target_condition_index', '0')
						target_idx = int(target_str)
					except: pass
					
					# 목록에서 타겟 인덱스 찾기
					cond_list = response.get('data', [])
					if cond_list and len(cond_list) > target_idx:
						target_cond = cond_list[target_idx]
						# 데이터 형식: ["0", "오늘폭등"] or ["0^오늘폭등"] (API에 따라 다름, 리스트로 가정)
						# 아까 로그: [["0","오늘폭등"],["1","불기둥"]]
						
						cond_idx = target_cond[0]
						cond_name = target_cond[1]
						
						logger.info(f"🎯 타겟 조건식 선택: [{cond_idx}] {cond_name}")
						
						# 실시간 등록 요청 (CNSRREQ)
						# Git 히스토리 기반 수정 (seq, stex_tp 사용)
						req_param = {
							'trnm': 'CNSRREQ',
							'seq': str(cond_idx), # 조건식 인덱스
							'search_type': '1',   # 1: 실시간
							'stex_tp': 'K'        # 0: 전체, 1: 코스피, 2: 코스닥 (K가 성공했음)
						}
						await self.send_message(message=req_param)
						logger.info(f"✅ 조건검색 실시간 등록 요청 전송 (CNSRREQ): {cond_name} (seq={cond_idx})")
					else:
						logger.warning(f"⚠️ 타겟 조건식(Index {target_idx})을 찾을 수 없습니다. (목록 개수: {len(cond_list)})")

				if response.get('trnm') != 'PING':
					# logger.debug(f'실시간 시세 서버 응답 수신: {response}')

						# [수정] REAL(실시간) 및 CNSRREQ(초기조회) 모두 처리
						if response.get('trnm') in ['REAL', 'CNSRREQ'] and response.get('data'):
							items = response['data']
							trnm = response.get('trnm')
							
							if items:
								logger.info(f'[{trnm}] 조건식 성립 {len(items)}개 수신')
								
								parsed_items = []
								for item in items:
									try:
										jmcode = None
										rate = 0.0
										real_data = {}
										
										# 1. 종목 코드 추출
										if trnm == 'REAL' and 'values' in item:
											v = item['values']
											jmcode = v.get('9001', v.get('stk_cd'))
											# 등락률 (FID 12 또는 11)
											rate = float(v.get('12', v.get('11', v.get('pl_rt', 0.0))))
											# 현재가 저장 (FID 10)
											raw_price = v.get('10')
											if raw_price:
												price = abs(int(str(raw_price).replace(',','')))
												if jmcode: self.current_prices[jmcode.replace('A','')] = price
											
											# 추가 실시간 팩터 추출 (거래량 FID 13, 체결강도 FID 15 등)
											try:
												if v.get('13'): real_data['vol'] = int(str(v.get('13')).replace(',',''))
												if v.get('15'): real_data['strength'] = float(str(v.get('15')).replace(',',''))
											except: pass
										else:
											jmcode = item.get('stk_cd', item.get('jmcode', item.get('9001')))
											rate = float(item.get('12', item.get('11', item.get('pl_rt', 0.0))))
											# 초기조회(CNSRREQ) 시에도 데이터가 있으면 추출
											try:
												if item.get('13'): real_data['vol'] = int(str(item.get('13')).replace(',',''))
												if item.get('15'): real_data['strength'] = float(str(item.get('15')).replace(',',''))
											except: pass

										if jmcode:
											jmcode = str(jmcode).replace('A', '')
											
											# [Realtime Update] 보유 종목이면 현재가/수익률 즉시 갱신 (반응 속도 향상)
											if jmcode in self.purchased_stocks and price > 0:
												# 현재가 갱신 (봇 전역 공유용 current_prices는 위에서 갱신됨)
												# 추가로 check_n_sell 등에서 참조하는 메모리 객체가 있다면 갱신 필요
												pass

											# [Filter] 이미 보유 중인 종목은 대기열에 넣지 않음
											if jmcode not in self.purchased_stocks:
												parsed_items.append({'code': jmcode, 'rate': rate})
												# 대기열에 [등락률, 추가데이터] 형태로 저장
												self.candidate_queue[jmcode] = (rate, real_data)
									except: continue
								
								if parsed_items:
									logger.info(f"[Queue] {len(parsed_items)}개 신규 대기열 추가 (현재 총 대기: {len(self.candidate_queue)}개)")
									
									# [Trigger] 빈 자리가 있으면 프로세서 가동
									target_cnt = self.target_cnt_cache or 5.0
									current_cnt = len(self.purchased_stocks)
									if current_cnt < target_cnt:
										asyncio.create_task(self.process_candidates(current_cnt, target_cnt))
							else:
								logger.warning(f'[{trnm}] 수신된 데이터(items)가 비어있습니다.')
								logger.error(f"대기열 프로세서 트리거 실패: {e}")

			except websockets.ConnectionClosed:
				logger.warning('Connection closed by the server')
				self.connected = False
				if self.websocket:
					try:
						await self.websocket.close()
					except:
						pass
				
				# 연결 종료 콜백 호출
				if self.on_connection_closed:
					try:
						await self.on_connection_closed()
					except Exception as e:
						logger.error(f'콜백 실행 중 오류: {e}')
				break  # 루프 종료
			
			except json.JSONDecodeError as e:
				logger.error(f'JSON 파싱 오류: {e}')
				logger.error(f'수신한 원본 메시지: {raw_message if raw_message else "수신 실패"}')
				continue  # 다음 메시지 수신 계속
			
			except Exception as e:
				logger.error(f'receive_messages에서 예외 발생: {type(e).__name__}: {e}')
				logger.error(f'연결 상태: connected={self.connected}, websocket={self.websocket is not None}')
				
				# 연결이 끊어진 것으로 보이면 연결 상태 확인
				if self.websocket:
					try:
						# Event loop 체크
						try:
							loop = asyncio.get_running_loop()
						except RuntimeError:
							logger.warning('Event loop가 종료되어 연결 확인을 중단합니다.')
							break
						
						# 연결이 살아있는지 확인
						await asyncio.wait_for(self.websocket.ping(), timeout=2)
						logger.info('연결은 유지되고 있습니다. 메시지 수신 계속...')
						continue
					except RuntimeError as e:
						if "no running event loop" in str(e) or "Event loop is closed" in str(e):
							logger.warning(f'Event loop 종료로 인해 루프를 중단합니다: {e}')
							break
						else:
							logger.error(f'연결 확인 실패: {e}')
							self.connected = False
							if self.on_connection_closed:
								try:
									await self.on_connection_closed()
								except Exception as callback_e:
									logger.error(f'콜백 실행 중 오류: {callback_e}')
							break
					except Exception as ping_e:
						logger.error(f'연결 확인 실패: {ping_e}')
						self.connected = False
						if self.on_connection_closed:
							try:
								await self.on_connection_closed()
							except Exception as callback_e:
								logger.error(f'콜백 실행 중 오류: {callback_e}')
						break  # 루프 종료
				else:
					logger.error('websocket이 None입니다. 루프 종료')
					break  # 루프 종료
					
	def update_held_stocks(self, current_stocks_list):
		"""
		외부(bot.py 등)에서 주기적으로 조회한 잔고 리스트를 받아
		내부 purchased_stocks 집합을 동기화합니다.
		"""
		try:
			# 1. API 잔고 기준 현재 보유 코드 집합 생성
			api_held_codes = set()
			if current_stocks_list:
				for stock in current_stocks_list:
					code = stock.get('stk_cd', '').replace('A', '')
					if code:
						# [Fix] 내가 최근에 팔았으면(recently_sold), API가 가지고 있다고 해도 무시 (Ghost Killing)
						if code in self.recently_sold:
							# logger.info(f"[Sync] Ghost 무시: {code} (API 잔고에 있지만 최근 매도됨)")
							continue
						api_held_codes.add(code)
			
			# 2. 동기화 (기존 목록과 비교하여 로그 출력)
			# [Ghost Stock Filter] 최근 매도된 종목은 API 잔고에 있어도 무시 (60초간)
			current_ts = time.time()
			# Clean up old records (60초 지난 것 삭제)
			for code in list(self.recently_sold.keys()):
				if current_ts - self.recently_sold[code] > 60:
					del self.recently_sold[code]
			
			real_new_stocks = set()
			new_stocks_candidates = api_held_codes - self.purchased_stocks
			
			for code in new_stocks_candidates:
				if code in self.recently_sold:
					logger.info(f"[Sync] Ghost Stock 감지: {code} (API는 보유 중이라지만 방금 매도함) -> 목록 추가 제외")
					continue
				real_new_stocks.add(code)

			# [New] 체결 확인 로직 (Verification)
			# API에서 발견된 종목이 '검증 대기' 상태라면 -> '체결 확정' 처리
			confirmed_orders = set()
			for code in list(self.pending_orders.keys()):
				if code in api_held_codes: # API 잔고에 등장!
					logger.info(f"[체결 확인] {code}: 주문 정상 체결 확인됨 ({time.time() - self.pending_orders[code]:.1f}초 소요)")
					confirmed_orders.add(code)
					del self.pending_orders[code]
				elif time.time() - self.pending_orders[code] > 60: # 타임아웃
					logger.warning(f"[체결 실패] {code}: 60초간 API 잔고 미반영 -> 주문 실패/거부로 간주하고 대기 해제")
					del self.pending_orders[code]
					# 재진입 허용
			
			if confirmed_orders:
				# [Fix] 체결 확인된 종목이라도, 그 사이에 매도되었을 수 있으므로 Ghost Check 수행
				final_confirmed = set()
				for code in confirmed_orders:
					if code in self.recently_sold:
						logger.info(f"[Sync] 체결 확인되었으나 최근 매도됨(Ghost) -> 보유 목록 추가 제외: {code}")
					else:
						final_confirmed.add(code)
				real_new_stocks.update(final_confirmed)

			if real_new_stocks:
				logger.info(f"[Sync] 외부 매수 감지 및 체결 확인: {real_new_stocks} -> 보유 목록 추가")
				self.purchased_stocks.update(real_new_stocks)
				
				# [New] 새로운 종목이 감지되었으므로 실시간 등록(SetRealReg) 갱신
				# 비동기 함수이므로 태스크로 실행
				asyncio.create_task(self.register_stocks_realtime(list(self.purchased_stocks)))
			
			# 사라진 종목 (수동 매도 등)
			# 단, 매수 진행 중(buying_stocks)이거나 검증 대기(pending_orders)인 종목은 제외
			# [추가] 최근 매수 시도(60초 이내)가 있었던 종목도 제외 (API 잔고 반영 지연 대비)
			sold_stocks = self.purchased_stocks - api_held_codes
			real_sold = set()
			current_ts = time.time()
			
			for s in sold_stocks:
				# 매수 진행 중이거나, 검증 대기 중이거나, 최근 60초 이내에 매수한 이력이 있으면 삭제 보류
				last_buy = self.buy_last_time.get(s, 0)
				is_pending = s in self.pending_orders
				
				if s not in self.buying_stocks and not is_pending and (current_ts - last_buy > 60):
					real_sold.add(s)
			
			if real_sold:
				logger.warning(f"[Sync] 외부 매도 감지: {real_sold} -> 보유 목록 제거 및 재매수 제한 등록")
				for s in real_sold:
					self.purchased_stocks.discard(s)
					# [Fix] 수동 매도 건도 고스트 현상 방지 및 재진입 방지를 위해 등록
					self.recently_sold[s] = time.time()
					
					# [Time-Cut Fix] bot.py의 held_since 참조가 있다면 같이 정리
					if self.held_since_ref is not None and s in self.held_since_ref:
						del self.held_since_ref[s]
					
					# [Core Fix] 수동 매도된 종목의 내부 누적 매입금 데이터 초기화 및 재매수 방지 시간 기록
					# 이를 하지 않으면 check_n_buy에서 API 잔고(0)보다 내부 데이터(기존금액)를 우선하여 재매수할 수 있음
					try:
						reset_accumulation(s)
						# check_n_buy의 재매수 쿨다운도 활성화
						import check_n_buy
						check_n_buy.last_sold_times[s] = time.time()
					except: pass
				
				# [New] 종목이 매도되어 사라졌으므로 실시간 등록 리스트 갱신
				asyncio.create_task(self.register_stocks_realtime(list(self.purchased_stocks)))
			
			# [추가] 빈 자리가 감지되면 대기열 확인 및 매수 실행
			# update_held_stocks는 자리를 비우는 역할을 하므로, 자리가 났을 때 대기열 처리를 트리거해줍니다.
			try:
				target_cnt = self.target_cnt_cache if self.target_cnt_cache else 5.0
				current_cnt = len(self.purchased_stocks)
				if current_cnt < target_cnt and self.candidate_queue:
					# 비동기 처리 메서드 호출
					asyncio.create_task(self.process_candidates(current_cnt, target_cnt))
			except Exception as e:
				logger.error(f"대기열 처리 트리거 실패: {e}")
				
		except Exception as e:
			logger.error(f"보유 종목 동기화 중 오류: {e}")

	async def process_candidates(self, current_cnt, target_cnt):
		"""대기열에 있는 종목을 꺼내 매수를 시도합니다. (Priority Buffering)"""
		# [LifeCycle] 중지 상태면 즉시 중단
		if not self.connected or not self.keep_running:
			return

		# [동시성 제어] 이미 다른 태스크가 후보군을 처리 중이면 중단 (중복 매수 방지)
		if self.candidates_lock.locked():
			return
		
		# 락 획득
		await self.candidates_lock.acquire()
		self.is_processing_candidates = True
		
		try:
			# [Priority] 2.0초 -> 0.1초 단축 (빠른 매수 전환)
			logger.info(f"[Buffering] 후보군 수집 Checking... [Queue: {len(self.candidate_queue)}]")
			await asyncio.sleep(0.1)
			
			# [LifeCycle Check]
			if not self.connected or not self.keep_running:
				self.candidate_queue.clear()
				return

			logger.info(f"[Debug] Wake up. Queue size: {len(self.candidate_queue)}")
			
			# [Fix] 설정값 실시간 반영 (캐시 대신 실시간 조회)
			try:
				from get_setting import get_setting
				self.target_cnt_cache = float(get_setting('target_stock_count', 5.0))
			except:
				pass
			target_cnt = self.target_cnt_cache
			if target_cnt < 1: target_cnt = 1

			# [Fix] 봇 인식 vs 실제 잔고 불일치 방지 (Over-buying 방어)
			# 매수 시도 직전에 무조건 실잔고 확인을 수행하여 정확한 needed 계산
			from kiwoom_adapter import fn_kt00004 as get_my_stocks
			try:
				# API 실시간 잔고 확인
				real_stocks = await asyncio.get_event_loop().run_in_executor(None, get_my_stocks, self.token)
				real_cnt = len(real_stocks) if real_stocks else 0
				real_codes = {s.get('stk_cd', '').replace('A','') for s in real_stocks} if real_stocks else set()
				
				# '검증 대기(pending)'인 종목 합산
				pending_cnt = 0
				for pc in self.pending_orders:
					if pc.replace('A','') not in real_codes:
						pending_cnt += 1
				
				# 내부 상태(purchased_stocks) 강제 동기화
				if real_stocks is not None:
					self.update_held_stocks(real_stocks)
					
				# 현재 정확한 수량 계산
				current_cnt = len(self.purchased_stocks)
				needed = int(target_cnt - current_cnt)
				
				print(f"DEBUG: Internal Stocks: {self.purchased_stocks}")
				print(f"DEBUG: Real Stocks Count: {real_cnt}, Pending: {pending_cnt}")
				print(f"DEBUG: Selection Check - Cur: {current_cnt}, Target: {target_cnt}, Needed: {needed}")
				logger.info(f"[Selection Check] 실시간수량: {current_cnt} (실제 {real_cnt} + 대기 {pending_cnt}), 목표: {target_cnt}, 필요수: {needed}")
			except Exception as e:
				logger.error(f"매수 전 잔고 체크 실패 (안전 위해 중단): {e}")
				return
			
			if not self.candidate_queue:
				logger.warning("[Buffering] 대기열이 비어있어 매수 진행 불가 (조건검색 결과 없음 or 수신 대기 중)")
				return 

			if needed <= 0:
				logger.info(f"[Buffering] 목표 수량 달성 완료 ({current_cnt}/{int(target_cnt)}) - 대기열({len(self.candidate_queue)}개) 초기화")
				self.candidate_queue.clear() # 꽉 찼으면 대기열 비우고 종료 (다음 신호 대기)
				return

			logger.info(f"[Selection] 현재 {current_cnt}개 / 목표 {int(target_cnt)}개 -> 대기열({len(self.candidate_queue)}개) 중 상위 {needed}개 선별")
			
			# Priority Sort (Rate Descending)
			sorted_items = []
			if isinstance(self.candidate_queue, dict):
				# [Priority Logic] 등락률(rate) + 체결강도(strength/100) 복합 점수로 정렬
				# 가장 '쎈' 종목(힘과 상승폭의 결합)을 우선 선정합니다.
				def get_score(item):
					rate, data = item[1] if isinstance(item[1], tuple) else (item[1], {})
					strength = data.get('strength', 100.0) # 없으면 기본 100%
					return rate + (strength / 100.0)
				
				sorted_items = sorted(self.candidate_queue.items(), key=get_score, reverse=True)
			else:
				sorted_items = [(x, (0, {})) for x in self.candidate_queue]
			
			# Select All
			candidates_info = [(x[0], x[1][1] if isinstance(x[1], tuple) else {}) for x in sorted_items]
			
			# Remove Selected & Clear Queue
			self.candidate_queue.clear()
			
			for code, r_data in candidates_info:
				# [Fix] 이미 보유 중인 종목은 신규 진입 대상에서 제외
				# 단, 물타기(Watering)를 위해 check_n_buy로 진입은 허용해야 함
				if code in self.purchased_stocks:
					# logger.info(f"[Selection Pass] {code}: 이미 보유 중이나 물타기 체크를 위해 chk_n_buy 진입 허용")
					pass

				# 매수 진행 중 체크
				if code in self.buying_stocks: continue
				
				# [중요] 루프 도중에도 다른 스레드/비동기 작업에 의해 목표 수량이 채워졌는지 확인
				if len(self.purchased_stocks) >= target_cnt:
					logger.info(f"[Selection 중단] 목표 수량 달성 ({len(self.purchased_stocks)}/{target_cnt}) - 추가 매수 중단")
					break
				
				# [Pending Check] 검증 대기 중인 종목도 보유 수량으로 간주하여 중복 매수 방지
				if code in self.pending_orders:
					logger.info(f"[Selection Skip] {code}: 체결 검증 대기 중이므로 매수 스킵")
					continue
				
				self.buying_stocks.add(code)
				self.buy_last_time[code] = time.time()
				
				logger.info(f"[Priority Pick] {code} 선정 -> 매수 시도")

				# chk_n_buy 호출 (Lock 사용)
				async with self.buy_lock:
					try:
						# 다시 한 번 수량 체크
						if len(self.purchased_stocks) >= target_cnt:
							logger.info(f"[Lock 획득 후 중단] 목표 수량 달성 ({len(self.purchased_stocks)}/{target_cnt}) - {code} 매수 취소")
							break
							
						# [Fix] API 호출 최적화
						try:
							from kiwoom_adapter import get_api, get_account_data, get_balance
							api = get_api()
							loop = asyncio.get_event_loop()
							
							c_stocks_data = await loop.run_in_executor(None, get_account_data, 'N', '', self.token)
							c_stocks = c_stocks_data[0] if c_stocks_data else []
							await asyncio.sleep(0.5)
							
							c_balance_raw = await loop.run_in_executor(None, get_balance, 'N', '', self.token)
							c_balance_data = {
								'deposit': c_balance_raw[2],
								'net_asset': c_balance_raw[1]
							} if c_balance_raw else None
							await asyncio.sleep(0.5)
							
							out_orders = await loop.run_in_executor(None, api.get_outstanding_orders, self.token)
						except Exception as api_err:
							logger.error(f"[API Error] 매수 전 데이터 조회 실패: {api_err}")
							c_stocks, c_balance_data, out_orders = None, None, None

						success = await asyncio.get_event_loop().run_in_executor(
							None, chk_n_buy, code, self.token, c_stocks, c_balance_data, self.held_since_ref, out_orders, self.response_manager, r_data
						)
						
						if success:
							# [Fix] 매수 성공 시 즉시 '보유'로 처리하여 연속 매수 방지
							self.purchased_stocks.add(code)
							self.pending_orders[code] = time.time()
							logger.info(f"[주문 전송 성공] {code} -> 체결 검증 대기 목록 등록 (API 잔고 반영 대기)")
							
							# [Time-Cut Fix] 매수 즉시 타이머 등록 (API 지연 무관하게 정확한 시간 추적)
							if self.held_since_ref is not None:
								self.held_since_ref[code] = time.time()
								logger.info(f"[Time-Cut] {code} 타이머 즉시 등록 (신규 매수)")
							
							# [New] 매수 성공 즉시 실시간 등록(SetRealReg) 갱신
							asyncio.create_task(self.register_stocks_realtime(list(self.purchased_stocks)))
					finally:
						self.buying_stocks.discard(code)
					
		except Exception as e:
			import traceback
			logger.error(f"대기열 종목 처리 중 오류: {e}\n{traceback.format_exc()}")
		finally:
			self.is_processing_candidates = False
			if self.candidates_lock.locked():
				self.candidates_lock.release()
			# 처리 후에도 대기열에 남은게 있다면? (위에서 clear 했으므로 없음)
			if self.candidate_queue:
				logger.info(f"[Residual] 처리 중 유입된 대기열({len(self.candidate_queue)}개) 존재 -> 프로세서 재가동")
				# 재귀적으로 호출하지 않고 Task 생성 (Stack overflow 방지)
				asyncio.create_task(self.process_candidates(len(self.purchased_stocks), target_cnt))


	async def disconnect(self):
		"""WebSocket 연결 종료"""
		self.keep_running = False
		if self.connected and self.websocket:
			try:
				await self.websocket.close()
			except Exception as e:
				logger.error(f'WebSocket close error: {e}')
			finally:
				self.connected = False
				self.websocket = None
				logger.info('Disconnected from WebSocket server')

	async def start(self, token):
		"""
		실시간 검색을 시작합니다.
		Returns:
			bool: 성공 여부
		"""
		logger.info(f"🚀 [RT_SEARCH] start() 호출됨 (Token: {str(token)[:10]}...)")
		try:
			# [Mock Server Support] Mock 모드인지 확인
			from kiwoom.factory import get_api_status
			api_status = get_api_status()
			is_mock_mode = api_status.get('is_mock', False)
			logger.info(f"🔍 [RT_SEARCH] 현재 모드: {'MOCK' if is_mock_mode else 'REAL'}")
			
			# [User Request] Local Mock(파이썬 시뮬레이터) 대신 Broker Test Server 사용
			# 아래 코드를 주석 처리하여, 강제로 웹소켓 연결(Test Server URL) 시도
			if is_mock_mode:
				logger.info("🎮 Mock 모드 감지 - 실시간 검색을 Mock 시뮬레이션으로 대체합니다")
				return await self._start_mock_mode(token)
			
			# keep_running 플래그를 True로 리셋
			self.keep_running = True
			
			# [중요] 시작 시 내부 상태 초기화 (재시작 시 잔여 데이터로 인한 오작동 방지)
			self.buying_stocks.clear()
			self.purchased_stocks.clear()
			self.buy_last_time.clear()
			self.last_msg_time = time.time() # [New] 초기값 설정 (좀비 체크 활성화용)
			logger.info("[Debug] start() calling candidate_queue.clear()")
			self.candidate_queue.clear()
			logger.info("내부 상태(보유목록/쿨타임 등) 초기화 완료")
			
			# 이미 웹소켓이 돌고 있다면 종료
			if self.receive_task and not self.receive_task.done():
				self.receive_task.cancel()
				try:
					await self.receive_task
				except asyncio.CancelledError:
					pass
				self.receive_task = None
				await self.disconnect()

			# WebSocket 연결
			await self.connect(token)
			
			# 연결이 성공했는지 확인
			if not self.connected:
				logger.error('WebSocket 연결에 실패했습니다.')
				return False

			# WebSocket 메시지 수신을 백그라운드에서 실행합니다.
			self.receive_task = asyncio.create_task(self.receive_messages())

			# [중요 수정] 실시간 검색 시작 전, 현재 보유 종목을 봇 메모리에 등록
			# 이렇게 해야 재시작 직후 잔고가 봇 메모리에 반영되지 않아 발생하는 중복 매수(오버 매수)를 방지할 수 있습니다.
			try:
				current_stocks = get_my_stocks(token=token)
				if current_stocks:
					self.update_held_stocks(current_stocks)
					logger.info(f"초기 보유 종목 로드 완료: {len(self.purchased_stocks)}개 ({self.purchased_stocks})")
			except Exception as e:
				logger.error(f"초기 보유 종목 로드 실패: {e}")

			# [추가] 시작 시점에 목표 종목 수 캐싱 (런타임 파일 읽기 경합 방지)
			try:
				# settings.json에서 직접 로드 (get_setting 내부 로직 활용)
				self.target_cnt_cache = float(get_setting('target_stock_count', 5))
				logger.info(f"목표 종목 수 캐싱 완료: {self.target_cnt_cache}개 (설정값 로드)")
			except Exception as e:
				logger.error(f"목표 종목 수 로드 실패(기본값 5 사용): {e}")
				self.target_cnt_cache = 5.0
				
			seq = get_setting('search_seq', '0')
			
			# 실시간 항목 등록
			await asyncio.sleep(1)
			await self.send_message({ 
				'trnm': 'CNSRREQ', # 서비스명
				'seq': seq, # 조건검색식 일련번호
				'search_type': '1', # 조회타입
				'stex_tp': 'K', # 거래소구분
			}, token)
			
			logger.info(f'실시간 검색이 시작되었습니다. seq: {seq}')
			
			# [New] 자동 갱신 태스크 시작
			self.refresh_task = asyncio.create_task(self._auto_refresh_loop())
			
			# [Diagnostic] 강제 종목 주입 (테스트용)
			# 15초 뒤에 삼성전자(005930)를 강제로 발견한 것처럼 큐에 넣음
			async def inject_test_stock():
				await asyncio.sleep(15)
				logger.info("🧪 [Test] 삼성전자(005930) 강제 매수 신호 주입!")
				self.candidate_queue['005930'] = 10.0 # 등락률 10% 가정
				# process_candidates 트리거
				current_cnt = len(self.purchased_stocks)
				target_cnt = self.target_cnt_cache
				await self.process_candidates(current_cnt, target_cnt)

			asyncio.create_task(inject_test_stock())

			return True
			
		except Exception as e:
			logger.error(f'실시간 검색 시작 실패: {e}')
			return False

	async def request_condition_search(self):
		"""조건검색 목록을 즉시 재요청합니다."""
		# [Rate Limit] 너무 잦은 요청 방지 (2초)
		if not hasattr(self, 'last_cnsrreq_time'):
			self.last_cnsrreq_time = 0
			
		if time.time() - self.last_cnsrreq_time < 2.0:
			return

		if not (self.websocket and self.connected):
			logger.warning("[Condition Refresh 대기] WebSocket 미연결 상태... 재접속 대기 중")
			return

		try:
			self.last_cnsrreq_time = time.time()
			seq = get_setting('search_seq', '0')
			logger.info(f"🔍 [Condition Search Request] 조건식({seq}) 재요청 전송...")
			
			# 1. 실시간 검색 요청 (기존)
			await self.send_message({ 
				'trnm': 'CNSRREQ', 
				'seq': seq, 
				'search_type': '1', 
				'stex_tp': 'K', 
			}, self.token)
			
			# 2. 일반 조건검색 요청 (보완용 - 종목 리스트 즉시 수신 목적)
			await asyncio.sleep(0.5)
			await self.send_message({ 
				'trnm': 'CNSRREQ', 
				'seq': seq, 
				'search_type': '0', 
				'stex_tp': 'K', 
			}, self.token)
			
		except Exception as e:
			logger.error(f"조건검색 요청 실패: {e}")


	async def stop(self):
		"""
		웹소켓 연결을 종료하고 모든 배경 작업을 중단합니다.
		"""
		try:
			self.keep_running = False # [Fix] 의도적 중지 표시
			logger.info('실시간 검색 중지를 시작합니다...')
			
			# 0. 매수 프로세스 트래킹 종료
			if hasattr(self, 'processing_tasks') and self.processing_tasks:
				logger.info(f"실행 중인 매수 프로세스({len(self.processing_tasks)}개)를 정지합니다.")
				for t in self.processing_tasks:
					if not t.done(): t.cancel()
				self.processing_tasks = []
			
			# 대기열 비우기
			if hasattr(self, 'candidate_queue') and self.candidate_queue:
				self.candidate_queue.clear()

			# 1. 태스크 정리
			if self.refresh_task and not self.refresh_task.done():
				self.refresh_task.cancel()
				try: await self.refresh_task
				except: pass
			self.refresh_task = None
			
			if self.receive_task and not self.receive_task.done():
				self.receive_task.cancel()
				try:
					await self.receive_task
				except asyncio.CancelledError:
					pass
			self.receive_task = None
			
			await self.disconnect()
			
			logger.info('실시간 검색이 완전히 중지되었습니다.')
			return True
			
		except Exception as e:
			logger.error(f'실시간 검색 중지 실패: {e}')
			return False

	async def _start_mock_mode(self, token):
		logger.info('🎮 Mock 실시간 검색 시작')
		self.keep_running = True
		self.connected = True
		self.token = token
		self.buying_stocks.clear()
		self.purchased_stocks.clear()
		self.buy_last_time.clear()
		self.candidate_queue.clear()
		try:
			# [Fix] 초기 보유 조회 실패해도 검색은 시작할 수 있도록 분리
			from kiwoom_adapter import get_my_stocks
			current_stocks = get_my_stocks(token=token)
			if current_stocks:
				self.update_held_stocks(current_stocks)
				logger.info(f'🎮 Mock 초기 보유: {len(self.purchased_stocks)}개')
		except Exception as e:
			logger.error(f'초기 보유 로드 실패 (무시하고 진행): {e}')
		try:
			self.target_cnt_cache = float(get_setting('target_stock_count', 5))
		except:
			self.target_cnt_cache = 5.0
		self.receive_task = asyncio.create_task(self._mock_condition_search_loop())
		logger.info('✅ Mock 실시간 검색 준비 완료 (Loop Task Created)')
		return True
	
	async def _mock_condition_search_loop(self):
		logger.info('🎮 [가상 서버] 조건검색 루프 시작 (매 2초 진동)')
		while self.keep_running:
			# logger.debug("🎮 [가상 서버] 루프 회전 중...")
			# 매 루프마다 설정값 캐시 갱신
			try:
				self.target_cnt_cache = float(get_setting('target_stock_count', 5.0))
			except:
				pass
				
			try:
				import random
				# [Mod] 사용자 요청: 저가/동전주 전용 리스트 (비싼 종목 제거)
				mock_stocks = [
					# 대형 고가주
					'005930', '000660', '035420', '051910', '068270', '006400', '005490', 
					# 중형 중가주
					'035720', '105560', '055550', '000270', '005380', '012330', '028260',
					'096770', '009540', '003550', '066570', '018260', '352820',
					# 저가주
					'003280', '001250', '001520', '000890', '000040', '003850', '010100', '000320', '005110'
				]
				# 한 번에 3~7개 발견 (더 활발하게)
				selected = random.sample(mock_stocks, min(random.randint(3,7), len(mock_stocks)))
				# [로그 강화] 확실하게 로그가 남도록 함
				logger.info(f'🎮 Mock 진동: {len(selected)}개 종목 후보군 검토 중...')
				for code in selected:
					if code not in self.purchased_stocks and code not in self.buying_stocks:
						# 무조건 높은 등락률로 매수 유도
						rate = random.uniform(3.0, 7.0)
						self.candidate_queue[code] = rate
						logger.info(f'🎮 {code} ({rate:.1f}%) -> Mock 매수 대기열 등록')

				# [Test] 보유 종목도 매 루프마다 검사 (물타기 테스트용)
				for p_code in list(self.purchased_stocks):
					# 랜덤하게 가격 변동 주입 (-5 ~ +5%)
					p_rate = random.uniform(-5.0, 5.0)
					# 등락률보다는, 그냥 큐에 넣어주면 check_n_buy가 알아서 판단함
					if p_code not in self.candidate_queue:
						self.candidate_queue[p_code] = p_rate
						# logger.info(f"🎮 [Self-Check] 보유종목 {p_code} 검증 큐 투입")
				
				if self.candidate_queue:
					current_cnt = len(self.purchased_stocks)
					target_cnt = self.target_cnt_cache or 5.0
					if current_cnt < target_cnt:
						await self.process_candidates(current_cnt, target_cnt)
				
				# 대기 시간 단축: 15초 -> 3초
				await asyncio.sleep(3)
			except Exception as e:
				logger.error(f'🎮 Mock 루프 오류: {e}')
				await asyncio.sleep(10)
		logger.info('🎮 Mock 루프 종료')

	async def _auto_refresh_loop(self):
		"""
		[New] 실시간 조건검색 재요청 및 연결 관리 루프 (Connection Manager)
		Websocket 연결이 끊기거나 좀비 상태(데이터 수신 없음)가 되면 자동으로 복구합니다.
		"""
		logger.info("[Auto Refresh] 연결 관리 및 자동 갱신 루프 시작")
		while self.keep_running:
			try:
				# 1. 연결 상태 점검 및 복구
				is_alive = self.connected and self.websocket and not getattr(self.websocket, 'closed', False)

				
				# [Zombie Check] 연결은 되어있으나 데이터가 30초 이상 안 들어오면 강제 재접속
				last_time = getattr(self, 'last_msg_time', 0)
				# last_msg_time이 0이면(시작 직후) 패스, 값이 있는데 30초 지났으면 좀비
				if is_alive and last_time > 0 and (time.time() - last_time > 30):
					logger.warning(f"[Zombie Socket] 30초간 데이터 수신 없음 (Last: {time.time()-last_time:.1f}s ago) -> 강제 재접속")
					await self.websocket.close()
					is_alive = False # 아래 재접속 로직 진입
				
				if not is_alive:
					logger.warning("[Auto Reconnect] 소켓 연결 복구 시도...")
					self.connected = False
					
					# 재연결
					await self.connect(self.token)
					
					if self.connected:
						logger.info("[Auto Reconnect] 소켓 재연결 성공 -> 수신 태스크 및 조건식 복구")
						
						# 1) 수신 태스크 재시작
						if self.receive_task: self.receive_task.cancel()
						self.receive_task = asyncio.create_task(self.receive_messages())
						
						# 2) 조건식 재등록 (CNSRREQ)
						await asyncio.sleep(1)
						seq = get_setting('search_seq', '0')
						await self.send_message({ 
							'trnm': 'CNSRREQ', 
							'seq': seq, 
							'search_type': '1', 
							'stex_tp': 'K', 
						}, self.token)
						
						# 3) 잔고 동기화 (선택적)
						from kiwoom_adapter import fn_kt00004 as get_my_stocks
						try:
							raw_stocks = await asyncio.get_event_loop().run_in_executor(None, get_my_stocks, self.token)
							if raw_stocks: self.update_held_stocks(raw_stocks)
						except: pass
						
						# 4) 통신 시간 갱신 (좀비 방지)
						self.last_msg_time = time.time()
					else:
						logger.error("[Auto Reconnect] 재연결 실패. 5초 후 재시도")
						await asyncio.sleep(5)
						continue

				# 2. 정상 연결 상태 -> 갱신 요청 (Keep-Alive 성격)
				if self.connected:
					# 5초마다 조건검색 재요청 (서버가 잊지 않게)
					await self.request_condition_search()
				
				await asyncio.sleep(5) 
			except Exception as e:
				logger.error(f"[Auto Refresh] 루프 오류: {e}")
				await asyncio.sleep(5)
		logger.info("[Auto Refresh] 루프 종료")
