import time
from kiwoom_adapter import fn_kt00004, fn_kt10001, fn_kt00001, get_token
import datetime
import json
import os
from tel_send import tel_send
from get_setting import get_setting as cached_setting
from logger import logger
from database import log_trade_sync, update_high_price_sync, get_high_price_sync, clear_stock_status_sync, get_watering_step_count_sync
from math_analyzer import evaluate_exit_strength, evaluate_risk_strength
from utils import normalize_stock_code
import check_n_buy
from voice_generator import speak
from analyze_tools import calculate_rsi, get_rsi_for_timeframe

# [Safety] 모듈 로드 시간 기록 (재시작 직후 매도 방지용)
MODULE_LOAD_TIME = time.time()

# Aliases for compatibility
get_my_stocks = fn_kt00004
sell_stock = fn_kt10001
get_balance = fn_kt00001

# [AI 리스크 관리] 분할 매도 상태를 전역적으로 관리 (루프 간 유지)
# {code: timestamp} - 마지막 분할 매도 시간 기록
ai_partial_sold_history = {}

# [Turbo TS] 고점 기록 메모리 캐시 (DB 지연 박멸)
# {code: float_high_price}
HIGH_PRICE_MEM_CACHE = {}

def chk_n_sell(token=None, held_since=None, my_stocks=None, deposit_amt=None, outstanding_orders=None, realtime_prices=None):
	global ai_partial_sold_history, HIGH_PRICE_MEM_CACHE
	partially_sold_codes = set() # 한 루프 내 중복 방지용 로컬 세트

	# [설정 로드]
	try: TP_RATE = float(cached_setting('take_profit_rate', 10.0))
	except: TP_RATE = 10.0
	
	try: 
		SL_RATE = float(cached_setting('stop_loss_rate', -1.0))
		if SL_RATE > 0: SL_RATE = -SL_RATE # [Fix] 손절률은 항상 음수여야 함
	except: SL_RATE = -1.0
	
	# 트레일링 스탑
	try: USE_TRAILING = cached_setting('use_trailing_stop', True) # bool or str
	except: USE_TRAILING = True
	
	try: TS_ACTIVATION = float(cached_setting('trailing_stop_activation_rate', 1.5))
	except: TS_ACTIVATION = 1.5
	
	try: TS_CALLBACK = float(cached_setting('trailing_stop_callback_rate', 0.5))
	except: TS_CALLBACK = 0.5
	
	# 일반 설정
	target_cnt = float(cached_setting('target_stock_count', 1))
	# [Robust] 대소문자 구분 없이 처리
	single_strategy = str(cached_setting('single_stock_strategy', 'WATER')).upper()

	split_buy_cnt = int(cached_setting('split_buy_cnt', 5)) # 기본값 5
	if target_cnt < 1: target_cnt = 1

	sold_stocks = []
	sell_reasons = {}
	holdings_codes = []

	try:
		if my_stocks is None:
			my_stocks = get_my_stocks(token=token)
		
		# 보유 종목이 없는 경우
		if not my_stocks:
			logger.info(f"[CheckSell] 보유 종목 없음 (Token: {str(token)[:10]}...)")
			return True, [], [], {}
		
		# [Realtime Price Injection] 실시간 시세로 보유종목 정보 갱신
		if realtime_prices:
			for stock in my_stocks:
				code = normalize_stock_code(stock['stk_cd']).replace('A', '')
				if code in realtime_prices and realtime_prices[code] > 0:
					old_prc = int(stock.get('cur_prc', 0))
					new_prc = realtime_prices[code]
					
					# 평균단가 (없으면 현재가로 가정하여 0% 처리)
					avg_prc = int(stock.get('pchs_avg_pric', stock.get('avg_prc', 0)))
					if avg_prc > 0:
						# 수익률 재계산: ((현재가 - 평단) / 평단) * 100
						new_pl_rt = ((new_prc - avg_prc) / avg_prc) * 100
						
						# 기존 데이터 업데이트
						stock['cur_prc'] = new_prc
						stock['pl_rt'] = f"{new_pl_rt:.2f}"
						
						# 평가금액도 갱신 (보유수량 * 현재가)
						qty = int(stock.get('rmnd_qty', 0))
						stock['evlu_amt'] = new_prc * qty
						
						logger.info(f"⚡ [Fast Update] {code}: {old_prc} -> {new_prc}원 (수익률 {new_pl_rt:.2f}%) - 실시간 반영")

		# [자산 및 할당금액 계산]
		total_stock_eval = 0
		for stock in my_stocks:
			if 'evlu_amt' in stock and stock['evlu_amt']:
				total_stock_eval += int(stock['evlu_amt'])
			else:
				price = int(stock.get('cur_prc', 0))
				qty = int(stock.get('rmnd_qty', 0))
				total_stock_eval += price * qty
		
		try:
			if deposit_amt is None:
				_, _, deposit_amt = get_balance(token=token)
		except Exception as e:
			logger.error(f"예수금 조회 실패: {e}")
			deposit_amt = 0 
			
		net_asset = deposit_amt + total_stock_eval

		# [안전장치] 자산 0원 오류 방지
		if net_asset <= 0:
			logger.warning("[안전장치 발동] 총 자산이 0원으로 조회되어 매도 로직을 건너뜜")
			return True, [], [normalize_stock_code(s['stk_cd']) for s in my_stocks], {}
		
		# 할당금액 계산 (안정성을 위해 원금 기반 할당액 사용)
		# 유저 요청: 평가금 변동에 따른 단계 출렁임 방지
		# [Fix] total_buy_principal pre-calculation logic
		total_buy_principal = 0
		for s in my_stocks:
			try:
				p_amt = float(s.get('pchs_amt', s.get('pur_amt', 0)))
				if p_amt == 0:
					_q = int(float(str(s.get('rmnd_qty', s.get('hold_qty', s.get('qty', 0)))).replace(',', '')))
					_a = float(str(s.get('pchs_avg_pric', s.get('avg_prc', 0))).replace(',', ''))
					p_amt = _q * _a
				total_buy_principal += p_amt
			except: pass


		principal_basis = deposit_amt + total_buy_principal
		capital_ratio = float(cached_setting('trading_capital_ratio', 70)) / 100.0
		alloc_per_stock = (principal_basis * capital_ratio) / target_cnt
		if alloc_per_stock <= 0: alloc_per_stock = 1

		
		for stock in my_stocks:
			stock_code = normalize_stock_code(stock['stk_cd'])
			stock_name = stock['stk_nm']
			holdings_codes.append(stock_code) 
			rsi_1m = None # Initialize to avoid UnboundLocalError

			pl_rt = float(stock['pl_rt']) if stock['pl_rt'] else 0.0
			
			# [Realtime Price Injection] 실시간 시세를 사용하여 수익률 및 현재가 정밀화
			cur_prc_val = float(stock.get('cur_prc', 0))
			if realtime_prices and stock_code in realtime_prices:
				rt_prc = float(realtime_prices[stock_code])
				if rt_prc > 0:
					cur_prc_val = rt_prc
					# 실시간 가격 기준 수익률 재계산 (Account API 지연 극복)
					try:
						avg_prc = float(str(stock.get('pchs_avg_pric', stock.get('avg_prc', 0))).replace(',', ''))
						if avg_prc > 0:
							pl_rt = ((cur_prc_val - avg_prc) / avg_prc) * 100
					except: pass

			# [Robust Qty Extractor] 1주인데 이전 루프 변수가 남지 않도록 매 루프마다 새로 추출
			try:
				qty_raw = stock.get('rmnd_qty', stock.get('hold_qty', stock.get('qty', 0)))
				qty = int(float(str(qty_raw).replace(',', '')))
			except:
				qty = 0


			
			elapsed_str = ""
			if held_since and stock_code in held_since:
				minutes = (time.time() - held_since[stock_code]) / 60
				elapsed_str = f"Time={minutes:.0f}m, "

			# [단계 판독 - 금액 비중(Filled Ratio) 기반으로 완전 교체]
			# (수량 기반 log2 방식은 저가주에서 오류를 일으키므로 폐기)
			pchs_amt = 0
			if 'pur_amt' in stock and stock['pur_amt']: pchs_amt = int(stock['pur_amt'])
			elif 'pchs_amt' in stock and stock['pchs_amt']: pchs_amt = int(stock['pchs_amt'])
			else:
				try: pchs_amt = float(stock.get('pchs_avg_pric', 0)) * int(stock.get('rmnd_qty', 0))
				except: pchs_amt = 0
				
			# [Filled Ratio] 현재 보유 비중 계산 (배정 금액 대비)
			filled_ratio = pchs_amt / alloc_per_stock if alloc_per_stock > 0 else 0

			# [Step Calc] DB 기록 기반 단계 판독 (사용자 요청: 매수 명령 횟수 = 단계)
			mode_key = "REAL" if not cached_setting('use_mock_server', False) else "MOCK"
			cur_step = get_watering_step_count_sync(stock_code, mode=mode_key)

			# [Robust Fix] 수량이 적으면 비중(Ratio)이 높더라도 단계를 강제로 낮춤 (사용자 불편 해소)
			# 소액 계좌에서 1~2주만 사도 비중이 70%가 넘어 5차(MAX)로 판독되는 현상 방지
			if qty <= 1: cur_step = 1
			elif qty == 2 and cur_step > 2: cur_step = 2 
			elif qty == 3 and cur_step > 3: cur_step = 3
			elif qty <= 5 and cur_step > 4: cur_step = 4 # 5주 이하는 절대 MAX(5차)가 될 수 없음
			
			logger.info(f"[CheckSell] {stock_code} ({stock_name}): {elapsed_str}PL={pl_rt}%, Step={cur_step}차, Qty={qty}주, Weight={filled_ratio*100:.1f}%")
			
			# [Safety] 재시작 직후 안전장치 (Smart Warm-up)
			# 수익률이 -5%보다 좋으면(-1%, -3% 등) 60초간 매도 유예 (시장 상황 파악 및 오매도 방지)
			# 단, 이미 -5% 이하로 폭락 중인 종목(위험군)은 유예 없이 즉시 매도 체크 진행
			if (time.time() - MODULE_LOAD_TIME < 60) and (pl_rt > -5.0):
				continue

			# [Time-Cut 설정]
			TIME_CUT_MINUTES = cached_setting('time_cut_minutes', 30)
			TIME_CUT_PROFIT = float(cached_setting('time_cut_profit', 1.0))
			
			should_sell = False
			sell_reason = ""

			# [위에서 계산된 cur_step 및 filled_ratio 재사용]
			if cur_step > split_buy_cnt: cur_step = split_buy_cnt
			# [Stable MAX logic] 
			
			# [Step Info 생성] 매도 사유에 포함될 최종 단계 문자열
			step_info = f"{cur_step}차"
			if cur_step >= split_buy_cnt: step_info = "MAX"

			# --------------------------------------------------------------------------------
			# [PRIORITY 0] 상한가/급등 매도 (최우선 순위)
			# --------------------------------------------------------------------------------
			if not should_sell:
				ul_val = cached_setting('upper_limit_rate', 29.5) # [Safety] 29.5 복구
				try: UPPER_LIMIT = float(ul_val)
				except: UPPER_LIMIT = 29.5
				
				# [Double Check] API수익률 OR 실시간계산수익률 둘 중 하나라도 만족하면 매도
				if pl_rt >= UPPER_LIMIT:
					should_sell = True
					sell_reason = f"상한가({step_info})"
					logger.info(f"🚀 [LASTTRADE 상한가] {stock_name}: 수익률 {pl_rt}% >= {UPPER_LIMIT}% -> 즉시 매도 (Priority 0)")
					speak(f"축하합니다. {stock_name} 종목이 상한가에 도달하여 전량 매도합니다.")

			# [Early Stop Logic] 사용자 설정값(Early Stop Step) 적용
			# 기본값: 설정 없으면 '분할횟수-1' (자동)
			try:
				default_early = split_buy_cnt - 1
				if default_early < 1: default_early = 1
				early_stop_step = int(cached_setting('early_stop_step', default_early))
			except:
				early_stop_step = split_buy_cnt - 1
				
			# 현재 단계가 '조기 손절 단계' 이상이면 손절 조건 체크
			is_actually_max = (cur_step >= early_stop_step)

			# [Time-Cut 로직]
			if not should_sell and held_since and stock_code in held_since:

				elapsed_sec = time.time() - held_since[stock_code]
				time_cut_limit = TIME_CUT_MINUTES * 60
				
				if elapsed_sec >= time_cut_limit:
					if pl_rt < TIME_CUT_PROFIT:
						should_sell = True
						sell_reason = f"TimeCut({step_info}, {elapsed_sec/60:.0f}분)"
						logger.info(f"[Time-Cut] {stock_name}: {elapsed_sec/60:.0f}분 경과, 수익률({pl_rt}%) < 기준 -> 교체 매매")

			# 1. [트레일링 스탑] (Turbo TS: Memory Cache Optimized)
			if not should_sell and USE_TRAILING:
				# 고점 업데이트 (메모리 우선)
				if pl_rt >= TS_ACTIVATION:
					if cur_prc_val > 0:
						# 메모리 최신값 확인 및 업데이트
						mem_high = HIGH_PRICE_MEM_CACHE.get(stock_code, 0)
						if cur_prc_val > mem_high:
							HIGH_PRICE_MEM_CACHE[stock_code] = cur_prc_val
							# DB는 비동기적으로(또는 백그라운드에서) 업데이트하면 좋지만, 
							# 여기서는 지연 박멸을 위해 메모리만 즉시 갱신하고 루프 밖에서 처리하거나 그대로 둠
							# (지연의 주범인 sync 호출 제거)
				
				# 고점 로드 (메모리 우선, 없으면 DB에서 1회 로드)
				high_prc = HIGH_PRICE_MEM_CACHE.get(stock_code, 0)
				if high_prc <= 0:
					high_prc = get_high_price_sync(stock_code)
					if high_prc > 0:
						HIGH_PRICE_MEM_CACHE[stock_code] = high_prc
				
				if high_prc > 0:
					drop_rate = ((high_prc - cur_prc_val) / high_prc) * 100
					
					if drop_rate >= TS_CALLBACK and pl_rt > 0:
						should_sell = True
						sell_reason = f"TrailingStop({step_info})"
						logger.info(f"🛡️ [Turbo TS] {stock_name}: 고점({high_prc:,.0f}) 대비 {drop_rate:.2f}% 하락 (현재수익률: {pl_rt:.2f}%)")
						# 매도 성공 시 메모리 캐시 삭제는 아래 매도 로직 이후 수행

			# 2. [조기 손절 / MAX 손절 / AI 리스크 관리]
			if not should_sell and single_strategy == "WATER":
				# (1) AI 리스크 판단 (조기 손절 포함)
				from analyze_tools import get_rsi_for_timeframe as get_rsi
				rsi_1m = get_rsi(stock_code, '1m') if rsi_1m is None else rsi_1m
				
				if rsi_1m is not None:
					risk_action, risk_reason = evaluate_risk_strength(rsi_1m, pl_rt, cur_step)
					
					if risk_action == 'FULL_SELL':
						should_sell = True
						sell_reason = risk_reason
						logger.warning(f"✂️ [AI FULL SELL] {stock_name}: {risk_reason}")
					# [AI 리스크 매도 제어] 
					# 1. 한 루프(chk_n_sell 루프) 내 중복 매도 방지: stock_code not in partially_sold_codes
					# 2. 최근 분할 매도 이력이 있는 경우 5분간 추가 매도 유보 (Cascade 방지): ai_partial_sold_history 체크
					last_ai_sell = ai_partial_sold_history.get(stock_code, 0)
					is_cooldown = (time.time() - last_ai_sell < 300) # 5분 쿨다운
					
					if risk_action == 'PARTIAL_SELL' and stock_code not in partially_sold_codes and not is_cooldown and qty >= 2:
						sell_qty = qty // 2
						if sell_qty > 0:
							logger.info(f"⚖️ [AI 리스크 관리] {stock_name}: {risk_reason} -> {sell_qty}주(50%) 리스크 조절 매도")
							final_code = stock_code.replace('A', '')
							res_code, res_msg = sell_stock(final_code, sell_qty, token=token)
							
							if str(res_code) in ['0', 'SUCCESS']:
								partially_sold_codes.add(stock_code)
								ai_partial_sold_history[stock_code] = time.time() # 전역 히스토리에 기록
								tel_send(f"⚖️ [AI 리스크 관리] {stock_name}: {risk_reason} ({sell_qty}주 비중축소)")
								speak(f"리스크 관리 차원에서 {stock_name} 종목의 비중을 축소합니다.")
								qty -= sell_qty
								stock['rmnd_qty'] = qty
								try:
									from database_trading_log import log_sell_to_db
									trade_source = stock.get('trade_type', '-')
									log_sell_to_db(stock_code, stock_name, sell_qty, cur_prc_val, pl_rt, f"AI리스크({risk_reason})", mode_key, trade_source)
								except: pass
							else:
								logger.error(f"❌ [AI 리스크 매도] 실패: {res_msg}")

				# (2) 전역 손절 (-10% 등) - AI 판단과 별개로 최후의 보루
				GLOBAL_SL_VAL = float(cached_setting('global_loss_rate', -10.0))
				if not should_sell and pl_rt <= GLOBAL_SL_VAL:
					should_sell = True
					sell_reason = f"전역손절({step_info}/{pl_rt}%)"
					logger.warning(f"🚨 [전역 손절] {stock_name}: {pl_rt}% <= {GLOBAL_SL_VAL}%")
					speak(f"긴급 상황 발생. {stock_name} 종목이 전역 손절 기준에 도달하여 긴급 매도합니다.")

			# 3. [AI 분할 매도] (New)
			if not should_sell and stock_code not in partially_sold_codes:
				from analyze_tools import get_rsi_for_timeframe as get_rsi
				rsi_1m = get_rsi(stock_code, '1m') if rsi_1m is None else rsi_1m
				if rsi_1m is not None:
					action, reason = evaluate_exit_strength(rsi_1m, pl_rt)
					if action == 'PARTIAL_SELL' and qty >= 2:
						# 절반 매도 실행
						sell_qty = qty // 2
						if sell_qty > 0:
							logger.info(f"⚖️ [AI판단 분할매도] {stock_name}: {reason} -> {sell_qty}주(50%) 부분 익절 진행")
							final_code = stock_code.replace('A', '')
							res_code, res_msg = sell_stock(final_code, sell_qty, token=token)
							
							if str(res_code) in ['0', 'SUCCESS']:
								partially_sold_codes.add(stock_code)
								tel_send(f"⚖️ [AI판단] {stock_name}: {reason} ({sell_qty}주 수익실현)")
								speak(f"인공지능 판단으로 {stock_name} 종목의 수익을 분할 실현합니다.")
								# 부분 매도 후에는 남은 수량으로 계속 감시 (루프 종료 안함)
								qty -= sell_qty
								stock['rmnd_qty'] = qty # 업데이트
								# DB 기록 (분할 매도 기록)
								try:
									from database_trading_log import log_sell_to_db
									trade_source = stock.get('trade_type', '-')
									log_sell_to_db(stock_code, stock_name, sell_qty, cur_prc_val, pl_rt, f"AI판단({reason})", mode_key, trade_source)
								except: pass
							else:
								logger.error(f"❌ [AI 분할 매도] 실패: {res_msg}")

			# 4. [일반 익절]
			if not should_sell:
				if pl_rt >= TP_RATE:
					should_sell = True
					sell_reason = f"익절({step_info})"
				elif pl_rt <= SL_RATE and single_strategy != "WATER":
					# WATER가 아닌 전략(FIRE 등)에서의 일반 손절
					should_sell = True
					sell_reason = f"손절({step_info})"



			# --------------------------------------------------------------------------------
			# [매도 실행]
			# --------------------------------------------------------------------------------
			if should_sell:
				# 미체결 매수 주문 취소
				try:
					current_orders = outstanding_orders
					if current_orders is None:
						from kiwoom_adapter import get_api
						api = get_api()
						current_orders = api.get_outstanding_orders(token)
					
					if current_orders:
						for order in current_orders:
							order_code = normalize_stock_code(order.get('stk_cd', order.get('code', '')))
							order_type = order.get('type', order.get('ord_tp', ''))
							# 매수 주문이면 취소
							if order_code == stock_code and (order_type == 'buy' or order_type == '01'):
								logger.warning(f"[미체결 취소] {stock_name}: 매도 전 미체결 매수 주문 취소")
								try:
									from kiwoom_adapter import get_api
									api = get_api()
									ord_no = order.get('ord_no', order.get('org_ord_no', ''))
									qty = order.get('qty', 0)
									if ord_no and qty > 0:
										api.cancel_stock(stock_code, str(qty), ord_no, token)
										time.sleep(0.5) 
								except: pass
				except: pass
				
				# 매도 중 상태 등록
				import config
				config.stocks_being_sold.add(stock_code)
				logger.info(f"[매도 주문 시작] {stock_name}: stocks_being_sold에 추가")
				
				if sell_reason != "상한가":
					time.sleep(0.5)
					
				# [매도 API 호출]
				# [Fix] 종목코드 A 제거 재확인 (API 호환성)
				final_code = stock_code.replace('A', '')
				return_code, return_msg = sell_stock(final_code, stock['rmnd_qty'], token=token)
				
				# 성공 확인 (Real=0, Mock=SUCCESS)
				if str(return_code) not in ['0', 'SUCCESS']:
					logger.error(f"[매도 실패] {stock['stk_nm']} ({stock_code}): {return_msg}")
					if stock_code in config.stocks_being_sold:
						config.stocks_being_sold.remove(stock_code)
					
					# Ghost Stock 처리
					if '800033' in str(return_msg): # 매도수량 부족 -> 잔고 없음
						logger.warning(f"[Ghost Stock 감지] {stock_name}: 강제 삭제 처리")
						# [Turbo TS] 고스트 종목도 캐시 삭제
						if stock_code in HIGH_PRICE_MEM_CACHE:
							del HIGH_PRICE_MEM_CACHE[stock_code]
						sold_stocks.append(stock_code)
					continue
				
				# [Turbo TS] 매도 성공 시 메모리 캐시 삭제 (다음 매매를 위해 리셋)
				if stock_code in HIGH_PRICE_MEM_CACHE:
					del HIGH_PRICE_MEM_CACHE[stock_code]
					logger.info(f"[Turbo TS] {stock_name} 고점 기록 리셋 완료")

				# [Source Fix] 가공하지 말고 실제 필드값 사용
				trade_source = stock.get('trade_type', '-')
				final_reason_text = sell_reason
				sell_reasons[stock_code] = final_reason_text

				# [DB 기록]
				try:
					from database_trading_log import log_sell_to_db
					from kiwoom_adapter import get_current_api_mode
					mode = get_current_api_mode().upper() 
					# [Fix] 가공하지 않은 사유와 소스 사용
					log_sell_to_db(stock_code, stock['stk_nm'], int(stock['rmnd_qty']), int(stock.get('cur_prc', 0)), pl_rt, final_reason_text, mode, trade_source)
				except Exception as e:
					logger.error(f"매도 로그 DB 저장 실패: {e}")
				
				# 정리
				clear_stock_status_sync(stock_code)
				try: 
					check_n_buy.reset_accumulation(stock_code)
					# [Fix] 매도 시 보유 시간 기록 삭제 (재매수 시 0분부터 시작)
					from database_helpers import delete_held_time
					delete_held_time(stock_code)
				except: pass
				
				# 매도 완료 상태 해제 (지연)
				import threading
				def remove_from_being_sold():
					time.sleep(5)
					if stock_code in config.stocks_being_sold:
						config.stocks_being_sold.remove(stock_code)
					if stock_code in partially_sold_codes:
						partially_sold_codes.discard(stock_code)
					
					# [AI] 전량 매도 완료 시 리스크 관리 이력도 완전 초기화
					if stock_code in ai_partial_sold_history:
						del ai_partial_sold_history[stock_code]
						
					logger.info(f"[매도 완료] {stock_name}: 매도 상태 및 AI 리스크 기록 해제")
				threading.Thread(target=remove_from_being_sold, daemon=True).start()

				# 텔레그램 전송
				# 텔레그램 전송
				result_emoji = "🔴" if pl_rt > 0 else "🔵"
				# [LASTTRADE] 시스템 명칭 포함 및 포맷 통일
				message = f'[{mode}] {result_emoji} LASTTRADE 매도 완료: {stock["stk_nm"]} {int(stock["rmnd_qty"])}주 ({sell_reason}) [수익률: {pl_rt}%]'
				tel_send(message)
				logger.info(message)
				
				sold_stocks.append(stock_code)
				
				# 재매수 쿨다운 (전량 매도일 때만 적용하여, 분할 매도 후 AI가 다시 사는 것 허용)
				is_partial_sell = "축소" in sell_reason or "분할" in sell_reason or "PARTIAL" in sell_reason
				
				if not is_partial_sell:
					check_n_buy.last_sold_times[stock_code] = time.time()
				else:
					logger.info(f"⚖️ [AI Trading] {stock_code}: 분할 매도이므로 재매수 쿨다운 미적용 (즉시 재진입 가능)")

				# [Cleanup] 장중 중복 학습 트리거 제거 (장 마감 후 bot.py에서 1회만 수행 권장)
				pass

		return True, sold_stocks, holdings_codes, sell_reasons

	except Exception as e:
		print(f"오류 발생(chk_n_sell): {e}")
		return False, [], [], {}

if __name__ == "__main__":
	chk_n_sell(token=get_token())