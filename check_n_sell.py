import time
from kiwoom_adapter import fn_kt00004, fn_kt10001, fn_kt00001
import datetime
import json
import os
from tel_send import tel_send
from get_setting import get_setting as cached_setting
from logger import logger
from database import log_trade_sync, update_high_price_sync, get_high_price_sync, clear_stock_status_sync
from utils import normalize_stock_code
# [재매수 방지] check_n_buy의 last_sold_times import
import check_n_buy

# Aliases for compatibility
get_my_stocks = fn_kt00004
sell_stock = fn_kt10001
get_balance = fn_kt00001

def chk_n_sell(token=None, held_since=None, my_stocks=None, deposit_amt=None, outstanding_orders=None):

	# 익절 수익율(%) - 목표 수익율에 도달하면 매도
	TP_RATE = cached_setting('take_profit_rate', 10.0)
	# 손절 수익율(%) - 손실 한계에 도달하면 매도
	SL_RATE = cached_setting('stop_loss_rate', -10.0)
	
	# 트레일링 스탑 설정 로드
	USE_TRAILING = cached_setting('use_trailing_stop', True)
	# [수정] 기본값 3.0% -> 1.5%로 조정 (사용자 요청 반영 및 합리적 수준)
	TS_ACTIVATION = cached_setting('trailing_stop_activation_rate', 1.5)
	# [수정] 기본값 1.5% -> 0.5%로 조정 (빠른 익절 대응)
	TS_CALLBACK = cached_setting('trailing_stop_callback_rate', 0.5)
	
	# 설정 로드
	target_cnt = float(cached_setting('target_stock_count', 5))
	single_strategy = cached_setting('single_stock_strategy', 'FIRE')
	split_buy_cnt = int(cached_setting('split_buy_cnt', 5))
	if target_cnt < 1: target_cnt = 1

	# 매도된 종목 리스트
	sold_stocks = []
	# [NEW] 매도 사유 딕셔너리 {code: reason}
	sell_reasons = {}
	# 현재 보유 중인 종목 리스트 (동기화용)
	holdings_codes = []

	try:
		# [Fix] 외부 주입 데이터 사용 (API 중복 호출 방지)
		if my_stocks is None:
			my_stocks = get_my_stocks(token=token)
		
		# 보유 종목이 없는 경우
		if not my_stocks:
			logger.info(f"[CheckSell] 보유 종목 없음 (Token: {str(token)[:10]}...)")
			return True, [], [], {}
			
		# [자산 및 할당금액 계산]
		# API 호출 최소화를 위해 my_stocks 데이터를 활용하여 주식 평가액 계산
		total_stock_eval = 0
		for stock in my_stocks:
			# evlu_amt(평가금액) 사용, 없으면 계산
			if 'evlu_amt' in stock and stock['evlu_amt']:
				total_stock_eval += int(stock['evlu_amt'])
			else:
				price = int(stock.get('cur_prc', 0))
				qty = int(stock.get('rmnd_qty', 0))
				total_stock_eval += price * qty
		
		try:
			# [Fix] 외부 주입 예수금 데이터 사용
			if deposit_amt is None:
				_, _, deposit_amt = get_balance(token=token)
		except Exception as e:
			logger.error(f"예수금 조회 실패: {e}")
			deposit_amt = 0 # 조회 실패 시 0 처리 (보수적 접근)
			
		net_asset = deposit_amt + total_stock_eval

		# [안전장치] 자산이 0원으로 조회되면 API 오류로 판단하여 매도 중단
		# 이유: 자산이 0이면 종목당 할당금액(alloc_per_stock)도 0이 되어, 
		#       모든 보유 종목이 "매집 완료" 상태로 오인받아 손절(StopLoss)이 잘못 나갈 수 있음.
		if net_asset <= 0:
			logger.warning("[안전장치 발동] 총 자산이 0원으로 조회되어 매도 로직을 건너뜜")
			# 성공으로 반환하되, 매도 리스트는 비움. 
			# holdings_codes는 반환해야 MainApp에서 보유종목 동기화에 사용됨 (0개라도 반환)
			# 하지만 my_stocks는 있으므로 holdings_codes를 채워서 반환하는 것이 맞음.
			return True, [], [normalize_stock_code(s['stk_cd']) for s in my_stocks], {}
		
		# [수정] 설정된 매매 자금 비율(trading_capital_ratio)을 사용하여 할당금액 계산
		capital_ratio = float(cached_setting('trading_capital_ratio', 70)) / 100.0
		alloc_per_stock = (net_asset * capital_ratio) / target_cnt
		if alloc_per_stock <= 0: alloc_per_stock = 1 # 방어
		
		for stock in my_stocks:
			stock_code = normalize_stock_code(stock['stk_cd'])
			stock_name = stock['stk_nm']
			holdings_codes.append(stock_code) # 보유 종목 리스트에 추가

			# pl_rt는 문자열이므로 float으로 변환하여 비교해야 함
			pl_rt = float(stock['pl_rt']) if stock['pl_rt'] else 0.0
			
			elapsed_str = ""
			if held_since and stock_code in held_since:
				minutes = (time.time() - held_since[stock_code]) / 60
				elapsed_str = f"Time={minutes:.0f}m, "

			logger.info(f"[CheckSell] {stock_code} ({stock_name}): {elapsed_str}PL={pl_rt}%, Strategy={single_strategy}, SL={SL_RATE}%")
			
			# [Time-Cut 전략] (우선 순위 최상위로 이동)
			# 조건: 설정 시간 이상 보유했고, 수익률이 기준(설정값, 기본 1.0%) 미만인 경우 (지루함 컷)
			TIME_CUT_MINUTES = cached_setting('time_cut_minutes', 30)
			TIME_CUT_PROFIT = float(cached_setting('time_cut_profit', 1.0)) # 1%도 안 되면 자름
			
			should_sell = False # Reset for each stock
			sell_reason = ""

			if held_since and stock_code in held_since:
				held_time = held_since[stock_code]
				elapsed_sec = time.time() - held_time
				
				# [Debug] Time-Cut Status Logging
				logger.info(f"[TimeCutCheck] {stock_name}: 경과 {elapsed_sec/60:.1f}분 / 설정 {TIME_CUT_MINUTES}분 / 수익률 {pl_rt}%")

				time_cut_limit = TIME_CUT_MINUTES * 60
			else:
				logger.warning(f"[TimeCutCheck] {stock_name}: held_since 정보 없음 (Keys: {list(held_since.keys()) if held_since else 'None'})")
				time_cut_limit = 999999

			# [데이터 준비] 매입 금액 계산
			pchs_amt = 0
			if 'pur_amt' in stock and stock['pur_amt']: pchs_amt = int(stock['pur_amt'])
			elif 'pchs_amt' in stock and stock['pchs_amt']: pchs_amt = int(stock['pchs_amt'])
			else:
				try: pchs_amt = float(stock.get('pchs_avg_pric', 0)) * int(stock.get('rmnd_qty', 0))
				except: pchs_amt = 0

			if held_since and stock_code in held_since:
				if elapsed_sec >= time_cut_limit:
					# 목표 수익률과 상관없이 최소 기준 (예: 1.0%)
					if pl_rt < TIME_CUT_PROFIT:
						# [대원칙] 매집 중에는 시간컷도 스킵
						# 목표 할당 금액의 95% 미만이면 매집 중으로 판단
						if pchs_amt < alloc_per_stock * 0.95:
							logger.info(f"[시간컷 스킵] {stock_name}: 매집 진행 중")
							continue  # 시간컷 스킵
						
						should_sell = True
						sell_reason = f"TimeCut({elapsed_sec/60:.0f}분)"
						logger.info(f"[Time-Cut] {stock_name}: {elapsed_sec/60:.0f}분 경과, 수익률({pl_rt}%) < 기준({TIME_CUT_PROFIT}%) -> 교체 매매 진행")

			# [물타기 전략 절대 원칙] 
			if single_strategy == "WATER":
				# 1. 절대 손실액 계산 (필드 호환성 + 직접 계산 + 수익률 역산)
				evlu_pnl = 0
				# 가능한 필드 체크
				for field in ['evlu_pnl', 'evpnl_amt', 'pnl_amt', 'pchs_pnl_amt']:
					if field in stock and stock[field]:
						try:
							evlu_pnl = float(stock[field])
							if evlu_pnl != 0: break
						except: continue
				
				# 0이면 직접 계산
				if evlu_pnl == 0:
					try:
						cur_prc = float(stock.get('cur_prc', 0))
						pchs_avg = float(stock.get('pchs_avg_pric', 0))
						qty = int(stock.get('rmnd_qty', 0))
						if cur_prc > 0 and pchs_avg > 0 and qty > 0:
							evlu_pnl = (cur_prc - pchs_avg) * qty
					except: pass
				
				current_loss_amt = abs(evlu_pnl) if evlu_pnl < 0 else 0
				
				# [WATER 전략 엄격 적용] 5회 완료 전까지는 손절 금지, 완료 후 1.5% 초과 시 손절
				strategy_rate_water = float(cached_setting('single_stock_rate', 1.5))
				total_target_loss = alloc_per_stock * (strategy_rate_water / 100.0)
				
				# 슬리피지 보정 (1.5% 목표 달성을 위해 1.48% 수준에서 선제적 감시)
				precision_target_loss = total_target_loss * 0.985 
				
				is_accumulated = (pchs_amt >= alloc_per_stock * 0.95)
				is_over_loss = (current_loss_amt > precision_target_loss)

				# [판단] 매집 완료 AND 손실 한도 초과 시에만 손절
				if is_accumulated and is_over_loss:
					logger.info(f"🚨 [WATER 손절] {stock_name}: 5회 매집 완료({int(pchs_amt/alloc_per_stock*100)}%) 및 손실({int(current_loss_amt):,}원) > 한도({int(total_target_loss):,}원) -> 즉시 매도")
					should_sell = True
					sell_reason = f"WATER손절({pl_rt}%)"
				elif not is_accumulated:
					# 매집 중에는 손절액을 넘었더라도 물타기를 위해 보유 (엔진에서 물타기 수행)
					if is_over_loss:
						logger.info(f"💧 [WATER 대기] {stock_name}: 손실액({int(current_loss_amt):,}원) 초과이나 매집 중({int(pchs_amt/alloc_per_stock*100)}%)이므로 물타기 진행")
					else:
						# 조용한 로깅
						pass
					if not should_sell: pass # SL_RATE 차단

			# [트레일링 스탑 로직]
			# TS는 물타기 완성 여부와 상관없이 무조건 실행 (익절 기회 보호)
			# should_sell = False (위에서 True 됐을 수도 있음)
			# sell_reason = ""
			
			if USE_TRAILING:
				# 1. 고점 갱신 시도 (수익률이 발동 수익률 이상일 때만 의미 있음, 하지만 데이터 축적 위해 매번)
				# 단, 발동 수익률 이상일 때만 DB 업데이트하여 I/O를 줄일 수도 있으나,
				# 정확한 고점 추적을 위해 매번 하되, DB 함수 내부에서 cur > high 일 때만 쓰기하므로 괜찮음.
				# 1. 고점 갱신 및 조건 체크
				# [개선] 현재 수익률이 활성화 기준(TS_ACTIVATION)을 넘었을 때만 고점을 기록하고 감시 시작
				if pl_rt >= TS_ACTIVATION:
					cur_prc = float(stock.get('cur_prc', 0))
					if cur_prc > 0:
						update_high_price_sync(stock_code, cur_prc)
				
				# 2. 트레일링 스탑 실행 체크
				high_prc = get_high_price_sync(stock_code)
				if high_prc > 0:
					cur_prc = float(stock.get('cur_prc', 0))
					drop_rate = ((high_prc - cur_prc) / high_prc) * 100
					
					# [핵심] 고점 대비 하락했으면서, 동시에 현재 수익률이 여전히 플러스(+)인 경우에만 익절
					if drop_rate >= TS_CALLBACK and pl_rt > 0:
						should_sell = True
						sell_reason = "TrailingStop"
						logger.info(f"[트레일링 스탑 발동] {stock_name}: 고점({high_prc}) 대비 {drop_rate:.2f}% 하락 (익절 수익률: {pl_rt}%)")

			# [상한가 매도] 사용자 요청: 상한가 도달 시 다른 조건(TimeCut 등) 기다리지 않고 즉시 매도
			# 설정된 상한가 기준(기본 29.5%) 이상이면 즉시 차익 실현
			ul_val = cached_setting('upper_limit_rate', 29.5)
			try:
				UPPER_LIMIT = float(ul_val)
			except:
				UPPER_LIMIT = 29.5 # Fallback on error
				
			if pl_rt >= UPPER_LIMIT:
				should_sell = True
				sell_reason = "상한가(UpperLimit)"
				logger.info(f"[상한가 감지] {stock_name}: 수익률 {pl_rt}% >= {UPPER_LIMIT}% -> 즉시 매도 진행")

			# 기존 익절/손절 체크
			if pl_rt > TP_RATE:
				should_sell = True
				sell_reason = "익절"
			elif pl_rt < SL_RATE and single_strategy == "FIRE":
				should_sell = True
				sell_reason = "손절(FIRE)"

			if should_sell:
				# [대원칙] 미체결 매수 주문 확인 및 취소
				try:
					# [Fix] 인자로 받은 outstanding_orders 사용
					current_orders = outstanding_orders
					if current_orders is None:
						from kiwoom_adapter import get_api
						api = get_api()
						current_orders = api.get_outstanding_orders(token)
					
					if current_orders:
						for order in current_orders:
							order_code = normalize_stock_code(order.get('stk_cd', order.get('code', '')))
							order_type = order.get('type', order.get('ord_tp', ''))
							
							# 해당 종목의 미체결 매수 주문이 있으면 취소
							if order_code == stock_code:
								if order_type == 'buy' or order_type == '01':
									logger.warning(f"[미체결 취소] {stock_name}: 매도 전 미체결 매수 주문 취소")
									try:
										from kiwoom_adapter import get_api
										api = get_api()
										ord_no = order.get('ord_no', order.get('org_ord_no', ''))
										qty = order.get('qty', 0)
										if ord_no and qty > 0:
											api.cancel_stock(stock_code, str(qty), ord_no, token)
											logger.info(f"[미체결 취소 완료] {stock_name}: 주문번호 {ord_no}")
											time.sleep(0.5)  # 취소 반영 대기
									except Exception as cancel_err:
										logger.error(f"[미체결 취소 실패] {stock_name}: {cancel_err}")
				except Exception as e:
					logger.warning(f"[미체결 확인 실패] {stock_name}: {e}")
				
				# [대원칙] 매도 주문 전송 시 stocks_being_sold에 추가
				import config
				config.stocks_being_sold.add(stock_code)
				logger.info(f"[매도 주문 시작] {stock_name}: stocks_being_sold에 추가")
				
				# 상한가 매도는 즉시 실행 (딜레이 없음)
				if sell_reason != "상한가":
					time.sleep(0.5)
				# 반환값: (return_code, return_msg)
				return_code, return_msg = sell_stock(stock_code, stock['rmnd_qty'], token=token)
				
				# API 리턴 코드는 문자열일 수도 있고 정수일 수도 있음. 안전하게 처리
				# [중요 수정] "SUCCESS" (Mock)와 "0" (Real) 모두 성공으로 처리
				if str(return_code) not in ['0', 'SUCCESS']:
					logger.error(f"[매도 실패] {stock['stk_nm']} ({stock_code}): {return_msg}")
					
					# [대원칙] 매도 실패 시 stocks_being_sold에서 제거
					if stock_code in config.stocks_being_sold:
						config.stocks_being_sold.remove(stock_code)
						logger.info(f"[매도 실패] {stock_name}: stocks_being_sold에서 제거")
					
					# [Fix] Ghost Stock 구별 강화
					# 800033: 모의투자 매도 가능 수량 부족 -> 실제 잔고가 없으므로 강제 청산 대상
					# 2000 / RC4025: 매수증거금 부족 등 -> 계좌 결함이지 종목이 없는 것이 아님. 강제 청산 금지!
					if '800033' in str(return_msg):
						logger.warning(f"[Ghost Stock 감지] {stock_name}: 실제 잔고 없음 -> 보유 목록에서 강제 삭제 처리")
						sold_stocks.append(stock_code) # 이렇게 하면 Main에서 삭제됨
					elif '2000' in str(return_msg) or '부족' in str(return_msg):
						logger.error(f"[매도 중단] {stock_name}: 계좌 상태 문제(증거금 등)로 매도 실패. 잔고는 유지됨.")
					
					continue

				# [Legacy] DB에 매매 기록 저장 (log_sell_to_db로 대체됨)
				# log_trade_sync("SELL", stock_code, stock['stk_nm'], int(stock['rmnd_qty']), int(stock.get('cur_prc', 0)), pl_rt, sell_reason)
				
				# [매매 로그 DB 저장 - 완전한 기록]
				try:
					from database_trading_log import log_sell_to_db
					from kiwoom_adapter import get_current_api_mode
					mode = get_current_api_mode().upper()  # "Mock" -> "MOCK"
					log_sell_to_db(stock_code, stock['stk_nm'], int(stock['rmnd_qty']), int(stock.get('cur_prc', 0)), pl_rt, sell_reason, mode)
				except Exception as e:
					logger.error(f"매도 로그 DB 저장 실패: {e}")
				
				# 봇 상태/DB 상태 초기화
				clear_stock_status_sync(stock_code)
				try:
					check_n_buy.reset_accumulation(stock_code)
				except: pass
				
				# [대원칙] 매도 성공 시 stocks_being_sold에서 제거 (일정 시간 후)
				# 즉시 제거하지 않고 5초 후 제거 (API 반영 시간 고려)
				import threading
				def remove_from_being_sold():
					time.sleep(5)
					if stock_code in config.stocks_being_sold:
						config.stocks_being_sold.remove(stock_code)
						logger.info(f"[매도 완료] {stock_name}: stocks_being_sold에서 제거 (5초 경과)")
				threading.Thread(target=remove_from_being_sold, daemon=True).start()

				# [Legacy] 매도 일지(sell_log.json) 저장 생략 (DB 기록으로 대체됨)
				pass

				if sell_reason in ["익절", "TrailingStop", "상한가", "상한가(강제)", "상한가(급등)"]:
					result_type = sell_reason
				else:
					result_type = "손절"
				result_emoji = "🔴" if pl_rt > TP_RATE else "🔵"
				message = f'{result_emoji} {stock["stk_nm"]} {int(stock["rmnd_qty"])}주 {result_type} 완료 (수익율: {pl_rt}%)'
				tel_send(message)
				logger.info(message)
				
				# 매도 성공 종목 추가
				sold_stocks.append(stock_code)
				sell_reasons[stock_code] = sell_reason # 매도 사유 저장
				
				# [재매수 방지] 매도 시간 기록 (타임컷 등 재매수 방지용)
				check_n_buy.last_sold_times[stock_code] = time.time()
				logger.info(f"[매도 기록] {stock_code}: 재매수 쿨다운 시작")

		return True, sold_stocks, holdings_codes, sell_reasons  # (성공여부, 매도리스트, 현재보유리스트, 매도사유)

	except Exception as e:
		print(f"오류 발생(chk_n_sell): {e}")
		return False, [], [], {}  # 예외 발생으로 실패

if __name__ == "__main__":
	chk_n_sell(token=get_token())