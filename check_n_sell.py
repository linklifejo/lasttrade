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

# Aliases for compatibility
get_my_stocks = fn_kt00004
sell_stock = fn_kt10001
get_balance = fn_kt00001

def chk_n_sell(token=None, held_since=None, my_stocks=None, deposit_amt=None, outstanding_orders=None):

	# [설정 로드]
	TP_RATE = cached_setting('take_profit_rate', 10.0)
	SL_RATE = cached_setting('stop_loss_rate', -10.0)
	
	# 트레일링 스탑
	USE_TRAILING = cached_setting('use_trailing_stop', True)
	TS_ACTIVATION = cached_setting('trailing_stop_activation_rate', 1.5)
	TS_CALLBACK = cached_setting('trailing_stop_callback_rate', 0.5)
	
	# 일반 설정
	target_cnt = float(cached_setting('target_stock_count', 5))
	single_strategy = cached_setting('single_stock_strategy', 'FIRE')
	split_buy_cnt = int(cached_setting('split_buy_cnt', 1)) # 기본값 1 (한 종목에 한 번만 진입)
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
		
		# 할당금액 계산
		capital_ratio = float(cached_setting('trading_capital_ratio', 70)) / 100.0
		alloc_per_stock = (net_asset * capital_ratio) / target_cnt
		if alloc_per_stock <= 0: alloc_per_stock = 1
		
		for stock in my_stocks:
			stock_code = normalize_stock_code(stock['stk_cd'])
			stock_name = stock['stk_nm']
			holdings_codes.append(stock_code) 

			pl_rt = float(stock['pl_rt']) if stock['pl_rt'] else 0.0
			
			elapsed_str = ""
			if held_since and stock_code in held_since:
				minutes = (time.time() - held_since[stock_code]) / 60
				elapsed_str = f"Time={minutes:.0f}m, "

			logger.info(f"[CheckSell] {stock_code} ({stock_name}): {elapsed_str}PL={pl_rt}%, Strategy={single_strategy}, SL={SL_RATE}%")
			
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

			# [단계 추정]
			cur_step = 0
			if 'watering_step' in stock:
				cur_step = int(stock['watering_step'])
			else:
				# [단계 추정 단순화]
				# 1회 설정이면 무조건 1차(MAX)로 간주 (보유하고 있으므로)
				if split_buy_cnt == 1:
					cur_step = 1
				else:
					if alloc_per_stock > 0:
						ratio = pchs_amt / alloc_per_stock
						cur_step = int(ratio * split_buy_cnt)
						if cur_step < 1: cur_step = 1

			# [Time-Cut 로직]
			if held_since and stock_code in held_since:
				elapsed_sec = time.time() - held_since[stock_code]
				time_cut_limit = TIME_CUT_MINUTES * 60
				
				if elapsed_sec >= time_cut_limit:
					if pl_rt < TIME_CUT_PROFIT:
						should_sell = True
						sell_reason = f"TimeCut({cur_step}차, {elapsed_sec/60:.0f}분)"
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
						sell_reason = f"TrailingStop({cur_step}차)"
						logger.info(f"🛡️ [LASTTRADE TS] {stock_name}: 고점({high_prc}) 대비 {drop_rate:.2f}% 하락 (익절 수익률: {pl_rt}%)")

			# 2. [물타기(WATER) 전략 특수 손절 로직]
			# 대원칙: 물타기 완료 후에는 추가 하락 시 즉시 매도하여 리스크 확정
			if not should_sell and single_strategy == "WATER":
				# [MAX 도달 판정] 
				if split_buy_cnt <= 1:
					is_max_bought = True
				else:
					# 실제 투입 금액이 할당액의 95% 이상이면 MAX로 간주
					is_max_bought = (cur_step >= split_buy_cnt) or (pchs_amt >= alloc_per_stock * 0.95)
				
				# [대원칙 예시 반영] 손절률이 1%일 때, 물타기 완료 후 -3% 도달 시 매도
				# 즉, SL_RATE보다 2% 더 하락한 지점을 임계치로 설정 (안전 마진)
				max_sl_trigger = SL_RATE - 2.0 
				if is_max_bought and pl_rt <= max_sl_trigger:
					should_sell = True
					sell_reason = f"WATER완성손절({cur_step}차)"
					logger.warning(f"🚨 [LASTTRADE WATER MAX] {stock_name}: 물타기 완료 후 추가 하락({pl_rt}% <= {max_sl_trigger}%) -> 즉시 매도")
				
				# 추가적으로, 물타기 완료 후 수익권에서 다시 손실로 전환되는 경우도 방어 (0% 하향 돌파 시)
				# (사용자 원칙의 '즉시 매도' 뉘앙스 반영)
				elif is_max_bought and pl_rt < -0.5 and SL_RATE > -1.0: # 타이트한 손절 설정 시
				    should_sell = True
				    sell_reason = f"MAX손실확정({cur_step}차)"

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
			if not should_sell:
				if pl_rt >= TP_RATE:
					should_sell = True
					sell_reason = f"익절({cur_step}차)"
				elif pl_rt <= SL_RATE:
					# WATER 전략은 위에서 MAX 단계별로 별도 처리했으므로, 여기서는 FIRE 또는 일반적인 경우 처리
					if single_strategy == "FIRE" or is_max_bought:
						should_sell = True
						sell_reason = f"손절({cur_step}차)"

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
				return_code, return_msg = sell_stock(stock_code, stock['rmnd_qty'], token=token)
				
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