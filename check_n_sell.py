import time
from kiwoom_adapter import fn_kt00004, fn_kt10001, fn_kt00001, get_token
import datetime
import json
import os
from tel_send import tel_send
from get_setting import get_setting as cached_setting
from logger import logger
from database import log_trade_sync, update_high_price_sync, get_high_price_sync, clear_stock_status_sync
from utils import normalize_stock_code
import check_n_buy

# [Safety] 모듈 로드 시간 기록 (재시작 직후 매도 방지용)
MODULE_LOAD_TIME = time.time()

# Aliases for compatibility
get_my_stocks = fn_kt00004
sell_stock = fn_kt10001
get_balance = fn_kt00001

def chk_n_sell(token=None, held_since=None, my_stocks=None, deposit_amt=None, outstanding_orders=None, realtime_prices=None):

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

			pl_rt = float(stock['pl_rt']) if stock['pl_rt'] else 0.0
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

			logger.info(f"[CheckSell] {stock_code} ({stock_name}): {elapsed_str}PL={pl_rt}%, Strategy={single_strategy}, SL={SL_RATE}%")
			
			# [Safety] 재시작 직후 안전장치 (Smart Warm-up)
			# 수익률이 -20%보다 좋으면(-10% 등) 60초간 매도 유예 (물타기 기회 부여)
			# 단, 이미 -20% 이하로 폭락 중이면 즉시 매도 허용
			if (time.time() - MODULE_LOAD_TIME < 60) and (pl_rt > -20.0):
				continue

			# [Time-Cut 설정]
			TIME_CUT_MINUTES = cached_setting('time_cut_minutes', 30)
			TIME_CUT_PROFIT = float(cached_setting('time_cut_profit', 1.0))
			
			should_sell = False
			sell_reason = ""

			# [매입 금액 계산]
			pchs_amt = 0
			if 'pur_amt' in stock and stock['pur_amt']: pchs_amt = int(stock['pur_amt'])
			elif 'pchs_amt' in stock and stock['pchs_amt']: pchs_amt = int(stock['pchs_amt'])
			else:
				try: pchs_amt = float(stock.get('pchs_avg_pric', 0)) * int(stock.get('rmnd_qty', 0))
				except: pchs_amt = 0

			# [단계 추정 정밀화 - LASTTRADE 수열 적용]
			# 1:1:2:4:8... 방식의 누적 비중 리스트 생성 (check_n_buy와 동일)
			weights = []
			for i in range(split_buy_cnt):
				if i == 0: weights.append(1)
				else: weights.append(2**(i - 1))
			total_weight = sum(weights)
			
			cumulative_ratios = []
			current_sum = 0
			for w in weights:
				current_sum += w
				cumulative_ratios.append(current_sum / total_weight)

			# 실제 투입 금액 기반 단계 판정
			cur_step = 1
			if alloc_per_stock > 0:
				# [소액 보정] 할당액이 적으면 금액 비율이 왜곡되므로 매입금액 기반 물리적 단계 적용
				if alloc_per_stock < 50000:
					# [Fix] 키 명칭 통일 (min_purchase_amount) 및 기본값 2000원 유지
					min_val = cached_setting('min_purchase_amount', 2000)
					try: min_amt = float(str(min_val).replace(',', ''))
					except: min_amt = 2000
					if min_amt < 100: min_amt = 2000 # 너무 작은 값 방지 (버그 방어)
					
					import math
					# [Intuition Fix] 수량이 1주라면 무조건 1차로 판정
					if qty <= 1:
						cur_step = 1
					else:
						cur_step = int(math.ceil(pchs_amt / min_amt))

					if cur_step > split_buy_cnt: cur_step = split_buy_cnt
					if cur_step < 1: cur_step = 1

				else:
					# [Intuition Fix] 수량이 1주라면 비중과 상관없이 무조건 1차로 판정
					if qty <= 1:
						cur_step = 1
					else:
						for i, ratio in enumerate(cumulative_ratios):
							# 현재 매입금이 해당 단계 비중의 98% 이상이면 그 단계로 인정
							if pchs_amt >= (alloc_per_stock * ratio * 0.98):
								cur_step = i + 1

			
			# [수정] 비중 90% 조건 삭제 (마틴게일 4차/5차 구분 명확화 필요)
			# [진짜 수정] 금액 비율(Ratio) 기반 MAX 판정 (UI와 동기화)
			# 금액이 할당량의 70% 이상이면, 설령 계산상 4차라도 MAX(5차) 급으로 간주하여 손절/익절 로직 적용
			filled_ratio = pchs_amt / alloc_per_stock if alloc_per_stock > 0 else 0
			# [Stable MAX logic] 
			# filled_ratio 임계값을 상향(0.7->0.95)하여 조금 더 여유를 줌
			is_max_bought = (cur_step >= split_buy_cnt) or (filled_ratio >= 0.95)
			# [Fix] 1주만 보유한 경우(qty=1), 예산상으로는 MAX더라도 전략상 '초동'으로 보아 손절 유예 대상이 됨
			is_actually_max = is_max_bought and (qty > 1 or single_strategy != "WATER")



			# [Time-Cut 로직]
			if held_since and stock_code in held_since:
				elapsed_sec = time.time() - held_since[stock_code]
				time_cut_limit = TIME_CUT_MINUTES * 60
				
				if elapsed_sec >= time_cut_limit:
					if pl_rt < TIME_CUT_PROFIT:
						should_sell = True
						display_step_str = f"{cur_step}차" if cur_step < split_buy_cnt else "MAX"
						sell_reason = f"TimeCut({display_step_str}, {elapsed_sec/60:.0f}분)"
						logger.info(f"[Time-Cut] {stock_name}: {elapsed_sec/60:.0f}분 경과, 수익률({pl_rt}%) < 기준 -> 교체 매매")

			# --------------------------------------------------------------------------------
			# [매도 판단 핵심 로직 - LASTTRADE 대원칙 준수]
			# --------------------------------------------------------------------------------

			# 1. [트레일링 스탑] (대원칙: TS는 우선적으로 발동한다)
			if USE_TRAILING:
				if pl_rt >= TS_ACTIVATION:
					cur_prc = float(stock.get('cur_prc', 0))
					if cur_prc > 0:
						update_high_price_sync(stock_code, cur_prc)
				
				high_prc = get_high_price_sync(stock_code)
				if high_prc > 0:
					cur_prc = float(stock.get('cur_prc', 0))
					drop_rate = ((high_prc - cur_prc) / high_prc) * 100
					
					if drop_rate >= TS_CALLBACK and pl_rt > 0:
						should_sell = True
						display_step_str = f"{cur_step}차" if cur_step < split_buy_cnt else "MAX"
						sell_reason = f"TrailingStop({display_step_str})"
						logger.info(f"🛡️ [LASTTRADE TS] {stock_name}: 고점({high_prc}) 대비 {drop_rate:.2f}% 하락 (익절 수익률: {pl_rt}%)")

			# 2. [물타기(WATER) 전략 특수 로직]
			if not should_sell and single_strategy == "WATER":
				# [조기 손절 (Early Stop)]
				# 원칙: 4차 매수 시 평단가는 -2% 수준으로 수렴함 (사용자 정의)
				# 여기서 '개별종목손절률'만큼 더 하락하면 5차(MAX) 진입 전 전량 손절
				# [Fix] 1주만 보유한 경우(qty=1)는 조기손절 대상에서 제외 (물타기 기회 보장)
				if cur_step == (split_buy_cnt - 1) and qty > 1:

					# 조기 손절 타겟 = -2.0% (4차 수렴 평단) - 개별종목손절률 (무조건 추가 하락분으로 처리)
					# Dashboard의 손절률이 3(%)이면 -2 - 3 = -5%에서 매도
					early_stop_target = -2.0 - abs(SL_RATE)
					
					if pl_rt <= early_stop_target:
						should_sell = True
						sell_reason = f"조기손절({cur_step}차)"
						logger.warning(f"✂️ [조기 손절] {stock_name}: 4차 수렴선(-2%) 대비 추가 하락({SL_RATE}%) 발생 -> 5차(MAX) 차단 (타겟:{early_stop_target}%, 현재:{pl_rt}%)")



			# 3. [상한가 매도]
			if not should_sell:
				ul_val = cached_setting('upper_limit_rate', 29.5)
				try: UPPER_LIMIT = float(ul_val)
				except: UPPER_LIMIT = 29.5
				if pl_rt >= UPPER_LIMIT:
					should_sell = True
					sell_reason = f"상한가({cur_step}차)"
					logger.info(f"🚀 [LASTTRADE 상한가] {stock_name}: 수익률 {pl_rt}% >= {UPPER_LIMIT}% -> 즉시 매도")

			# 4. [일반 익절/손절]
			# [원칙] WATER 전략에서는 1주(초기 진입) 상태에서 바로 손절을 나가지 않고 물타기를 기다립니다.
			if not should_sell:
				if pl_rt >= TP_RATE:
					should_sell = True
					sell_reason = f"익절({cur_step}차)"
				elif pl_rt <= SL_RATE:
					# [원칙] WATER 전략은 일반 손절을 사용하지 않습니다. (사용자 요청: 삭제)
					# 오직 FIRE 전략이거나 다른 특수 전략에서만 작동합니다.
					if single_strategy != "WATER":
						should_sell = True
						sell_reason = f"손절({cur_step}차)"
					else:
						# WATER 전략은 조기손절(Early Stop) 또는 고점 대비 하락(Trailing Stop)으로만 제어
						pass



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
						sold_stocks.append(stock_code)
					continue

				# [DB 기록]
				try:
					from database_trading_log import log_sell_to_db
					from kiwoom_adapter import get_current_api_mode
					mode = get_current_api_mode().upper() 
					log_sell_to_db(stock_code, stock['stk_nm'], int(stock['rmnd_qty']), int(stock.get('cur_prc', 0)), pl_rt, sell_reason, mode)
				except Exception as e:
					logger.error(f"매도 로그 DB 저장 실패: {e}")
				
				# 정리
				clear_stock_status_sync(stock_code)
				try: check_n_buy.reset_accumulation(stock_code)
				except: pass
				
				# 매도 완료 상태 해제 (지연)
				import threading
				def remove_from_being_sold():
					time.sleep(5)
					if stock_code in config.stocks_being_sold:
						config.stocks_being_sold.remove(stock_code)
						logger.info(f"[매도 완료] {stock_name}: 매도 상태 해제")
				threading.Thread(target=remove_from_being_sold, daemon=True).start()

				# 텔레그램 전송
				# 텔레그램 전송
				result_emoji = "🔴" if pl_rt > 0 else "🔵"
				# [LASTTRADE] 시스템 명칭 포함 및 포맷 통일
				message = f'[{mode}] {result_emoji} LASTTRADE 매도 완료: {stock["stk_nm"]} {int(stock["rmnd_qty"])}주 ({sell_reason}) [수익률: {pl_rt}%]'
				tel_send(message)
				logger.info(message)
				
				sold_stocks.append(stock_code)
				sell_reasons[stock_code] = sell_reason
				
				# 재매수 쿨다운
				check_n_buy.last_sold_times[stock_code] = time.time()

				# 학습 트리거
				try:
					import subprocess, sys
					python_executable = sys.executable
					script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'learn_daily.py')
					subprocess.Popen([python_executable, script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
				except: pass

		return True, sold_stocks, holdings_codes, sell_reasons

	except Exception as e:
		print(f"오류 발생(chk_n_sell): {e}")
		return False, [], [], {}

if __name__ == "__main__":
	chk_n_sell(token=get_token())