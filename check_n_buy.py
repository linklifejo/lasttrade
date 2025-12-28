import time
from kiwoom_adapter import fn_kt00001, fn_ka10004, fn_kt10000, fn_kt00004, get_total_eval_amt
from tel_send import tel_send
from get_setting import get_setting
from logger import logger
from analyze_tools import calculate_rsi, get_rsi_for_timeframe
from database import get_price_history_sync, log_signal_snapshot_sync
from technical_judge import technical_judge
from utils import normalize_stock_code
from stock_info import fn_ka10001 as stock_info

# Aliases for compatibility
get_balance = fn_kt00001
check_bid = fn_ka10004
buy_stock = fn_kt10000
get_my_stocks = fn_kt00004


# 종목별 마지막 매수 시간을 기록하는 딕셔너리 (메모리 상주)
last_buy_times = {}
# [재매수 방지] 종목별 마지막 매도 시간 기록 (타임컷 후 재매수 금지용)
last_sold_times = {}
# [추가] 종목별 누적 매수 금액 추적 (API 잔고 반영 지연 시 오버 매수 방지)
accumulated_purchase_amt = {}
# 매수 체크 함수
def chk_n_buy(stk_cd, token, current_holdings=None, current_balance_data=None, held_since=None, outstanding_orders=None, response_manager=None):
	global accumulated_purchase_amt # 전역 변수 사용
	global last_sold_times # 매도 시간 추적용
	
	logger.info(f'[매수 체크] 종목 코드: {stk_cd}')
	
	rsi_1m = None
	rsi_3m = None
	
	# [쿨타임 체크] 같은 종목을 너무 자주 매수하는 것을 방지 (기본 10분)
	# [쿨타임 체크] 같은 종목을 너무 자주 매수하는 것을 방지 (10분 -> 30초로 단축)
	# [쿨타임 체크] 같은 종목을 너무 자주 매수하는 것을 방지 (10분 -> 5초로 단축)
	buy_cooldown = 5 # 5초 (재진입 방지)
	last_time = last_buy_times.get(stk_cd, 0)
	if time.time() - last_time < buy_cooldown:
		logger.info(f"[매수 스킵] {stk_cd}: 매수 쿨타임 중 ({int(buy_cooldown - (time.time() - last_time))}초 남음)")
		return False

	# [재매수 방지] 최근 매도한 종목은 일정 시간 동안 재매수 금지
	sell_wait = int(get_setting('sell_rebuy_wait_seconds', 30)) # 초 단위 직접 사용
	last_sold_time = last_sold_times.get(stk_cd, 0)
	if last_sold_time > 0:
		elapsed = time.time() - last_sold_time
		if elapsed < sell_wait:
			remaining_min = int((sell_wait - elapsed) / 60)
			logger.info(f"[재매수 금지] {stk_cd}: 최근 매도 후 대기 중 ({remaining_min}분 남음)")
			return False
		else:
			# 쿨다운 시간이 지났으므로 기록 삭제 (메모리 정리)
			del last_sold_times[stk_cd]
			logger.info(f"[재매수 허용] {stk_cd}: 매도 후 {sell_wait/60:.0f}분 경과 -> 재매수 가능")

	# [대원칙] 매도 주문이 키움에 전달된 종목은 절대 매수 금지
	import config
	if stk_cd in config.stocks_being_sold:
		logger.warning(f"[매수 금지] {stk_cd}: 현재 매도 중(stocks_being_sold)인 종목입니다.")
		return False

	# [New] 안전장치: stocks_being_sold가 너무 비대해지는 것 방지 (5% 확률로 정리)
	import random
	if random.random() < 0.05:
		try:
			if outstanding_orders is not None:
				selling_codes = {normalize_stock_code(o.get('stk_cd', '')) for o in outstanding_orders if o.get('type') == 'sell' or o.get('ord_tp') == '02'}
				stuck_codes = config.stocks_being_sold - selling_codes
				for sc in stuck_codes:
					config.stocks_being_sold.discard(sc)
					logger.info(f"[Auto Clean] {sc} 가 유령 매도 목록에서 제거됨")
		except: pass

	# [대원칙] 미체결 주문 확인 및 잘못된 주문 취소
	try:
		# [Fix] 인자로 받은 outstanding_orders 사용 (API 호출 중복 방지)
		if outstanding_orders is None and token:
			try:
				from kiwoom_adapter import get_api
				api = get_api()
				outstanding_orders = api.get_outstanding_orders(token)
			except: pass
		
		if outstanding_orders:
			for order in outstanding_orders:
				order_code = normalize_stock_code(order.get('stk_cd', order.get('code', '')))
				order_type = order.get('type', order.get('ord_tp', ''))
				
				# 해당 종목의 미체결 주문이 있는지 확인
				if order_code == stk_cd:
					# 매도 주문이 미체결 상태면 매수 금지
					if order_type == 'sell' or order_type == '02':
						logger.warning(f"[매수 금지] {stk_cd}: 미체결 매도 주문 존재 - 매수 불가")
						return False
					
					# 매수 주문이 미체결 상태면 누적 (물타기는 누적되어야 함)
					if order_type == 'buy' or order_type == '01':
						pending_qty = order.get('qty', 0)
						logger.info(f"[물타기 누적] {stk_cd}: 기존 미체결 {pending_qty}주 유지, 추가 매수 진행")
						# 취소하지 않고 그대로 진행 (물타기 누적)
	except Exception as e:
		logger.warning(f"[미체결 확인 실패] {stk_cd}: {e}")
		# 미체결 확인 실패해도 매수는 진행 (API 오류 시 매수 차단 방지)

	# 1. 보유 종목 정보 조회 (보유 여부 및 수익률 확인)
	current_holding = None
	my_stocks_count = 0 
	
	try:
		# 인자로 전달받지 않은 경우에만 API 호출
		if current_holdings is None:
			current_holdings = get_my_stocks(token=token)
			
		if current_holdings:
			my_stocks_count = len(current_holdings)
			for stock in current_holdings:
				# 보유 종목 코드 'A' 제거 후 비교 (안전한 정규화)
				if normalize_stock_code(stock['stk_cd']) == stk_cd:
					current_holding = stock
					logger.info(f"보유 종목 상세: {stock.get('stk_nm')} / 평단: {stock.get('pchs_avg_pric')} / 현재가: {stock.get('cur_prc')} / 수량: {stock.get('rmnd_qty')} / 수익률: {stock.get('pl_rt')}")
					break
	except Exception as e:
		logger.error(f"[매수 체크] 보유종목 조회 오류: {e}")
		return False
	
	# [대원칙] 종목수 제한 및 종목별 한도 엄수
	# 설정값 미리 로드
	target_cnt = float(get_setting('target_stock_count', 5))
	if target_cnt < 1: target_cnt = 1
	
	# [추가] 개별 종목 비중 초과 체크 (5차/MAX 방어)
	if current_holding is not None:
		try:
			# 자산 정보를 미리 가져와서 할당액 계산 (위치 이동)
			total_eval_amt_est = float(get_total_eval_amt(token=token)) if not current_balance_data else float(current_balance_data.get('total_asset', current_balance_data.get('net_asset', 0)))
			cap_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0
			alloc_per_stock = (total_eval_amt_est * cap_ratio) / target_cnt
			
			if alloc_per_stock > 0:
				pchs_amt = float(current_holding.get('pchs_amt', current_holding.get('pur_amt', 0)))
				if pchs_amt == 0:
					pchs_amt = float(current_holding.get('pchs_avg_pric', 0)) * int(current_holding.get('rmnd_qty', 0))
				
				if pchs_amt >= alloc_per_stock * 0.98:
					logger.info(f"[매수 금지] {stk_cd}: 이미 종목별 최대 한도(MAX) 도달 - 추가 매수 절대 금지")
					return False
		except Exception as e:
			logger.warning(f"[한도 체크 스킵] {e}")

	# 신규 매수인 경우 (보유하지 않은 종목)
	if current_holding is None:
		# 이미 목표 종목 수에 도달했으면 신규 매수 금지
		if my_stocks_count >= int(target_cnt):
			logger.warning(f"[종목수 제한] {stk_cd}: 현재 {my_stocks_count}개 보유 중 (목표: {int(target_cnt)}개) - 신규 매수 불가")
			return False
		logger.info(f"[신규 매수 가능] {stk_cd}: 현재 {my_stocks_count}개 보유 중 (목표: {int(target_cnt)}개)")
		
	# time.sleep(0.3)
	
	try:
		# 2. 자산 조회: 순자산(예수금+주식) 기준
		# [최적화] 외부에서 주입받은 경우 재사용 (키 매핑 보정)
		if current_balance_data:
			# bot.py에서 넘겨주는 key는 'deposit'임
			balance = int(current_balance_data.get('deposit', 0))
			# 혹시 'balance'로 올 수도 있으니 체크
			if balance == 0: 
				balance = int(current_balance_data.get('balance', 0))
				
			deposit_amt = balance
			# 'net_asset' or 'total_asset'
			if 'total_asset' in current_balance_data:
				net_asset = int(current_balance_data.get('total_asset', 0))
			else:
				net_asset = int(current_balance_data.get('net_asset', 0))
				
			# stock_val 추정 (자산 - 현금)
			stock_val = net_asset - balance
		else:
			balance, _, deposit_amt = get_balance(token=token)
			stock_val = get_total_eval_amt(token=token)
			net_asset = deposit_amt + stock_val
		
		# [Fix] 예수금 0원 이슈 및 키 매핑 오류 대응
		if balance <= 0:
			# API가 deposit만 0으로 주는 경우 또는 키 매핑 실패 시 역산 시도
			estimated_deposit = net_asset - stock_val
			if estimated_deposit > 50000: # 5만원 이상이면 유효한 예수금으로 인정
				logger.warning(f"[Balance Fix] 잔고 0원 -> 추정 예수금({estimated_deposit:,.0f}원) 사용")
				balance = estimated_deposit
			else:
				logger.warning(f"주문가능한 잔고가 없습니다. (Balance:{balance}, Asset:{net_asset})")
				return False
			
	except Exception as e:
		logger.error(f"자산 조회 오류: {e}")
		return False
    
    # [방어 로직] 내부 추적 데이터 초기화 (만약 API에서 종목이 사라졌다면 매도된 것이므로 초기화)
	if current_holding is None and stk_cd in accumulated_purchase_amt:
		# 단, 쿨타임(30초) 이내라면 아직 API 반영 전일 수 있으므로 유지
		if time.time() - last_time > 30:
			logger.info(f"[데이터 보정] {stk_cd}: API 보유 목록에 없음 (30초 경과) -> 내부 누적 금액({accumulated_purchase_amt[stk_cd]}) 초기화")
			del accumulated_purchase_amt[stk_cd]

	# 3. 매수 자금 계산 로직
	# 설정값: 분할 매수 횟수(K) (target_cnt는 위에서 이미 로드됨)
	split_cnt_setting = float(get_setting('split_buy_cnt', 2))
	
	if split_cnt_setting < 1: split_cnt_setting = 1
	
	# [RSI 필터] 과매수(70 이상) 구간 매수 금지
	use_rsi = get_setting('use_rsi_filter', False)
	if use_rsi:
		# [Danta] 1분봉 및 3분봉 RSI 동시 체크
		rsi_1m = get_rsi_for_timeframe(stk_cd, '1m')
		rsi_3m = get_rsi_for_timeframe(stk_cd, '3m')
		
		rsi_val_str = str(get_setting('rsi_limit', 70)).strip()
		if not rsi_val_str: rsi_val_str = '70'
		rsi_limit = float(rsi_val_str)
			
		if rsi_1m is not None:
			logger.info(f"📊 [RSI] 1분봉: {rsi_1m:.2f} (한도: {rsi_limit})")
			if rsi_1m >= rsi_limit:
				logger.warning(f"[RSI 경고] {stk_cd} 1분봉 과매수({rsi_1m:.2f})")
				
		if rsi_3m is not None:
			logger.info(f"📊 [RSI] 3분봉: {rsi_3m:.2f}")

	# [New] Technical Judge - 종목 성향 및 보조지표 최종 판독
	is_passed, judge_msg = technical_judge.judge_buy(stk_cd)
	if not is_passed:
		logger.warning(f"⚖️ [Technical Judge] {stk_cd}: 매수 거절 - {judge_msg}")
		return False
	
	# [Math Probability Filter] 수학적 기대 승률 체크
	from math_analyzer import get_win_probability
	win_prob, sample_count = get_win_probability(rsi_1m)
	
	# 설정값 로드
	min_prob = float(get_setting('math_min_win_rate', 0.55)) # 최소 승률 55%
	min_count = int(get_setting('math_min_sample_count', 5))  # 최소 표본 5건
	
	# [Fix] rsi_1m 또는 win_prob가 None인 경우를 위한 안전한 포맷팅
	rsi_fmt = f"{rsi_1m:.2f}" if rsi_1m is not None else "N/A"
	prob_fmt = f"{win_prob*100:.1f}" if win_prob is not None else "N/A"
	logger.info(f"📊 [Math Filter] RSI_1m: {rsi_fmt} -> 기대 승률: {prob_fmt}% (표본: {sample_count}건)")
	
	# 데이터가 충분할 때만 승률 필터 적용
	math_weight = 1.0
	if sample_count >= min_count and win_prob is not None:
		if win_prob < min_prob:
			logger.warning(f"📉 [Math Filter] {stk_cd}: 기대 승률({win_prob*100:.1f}%)이 기준({min_prob*100:.0f}%) 미달하여 매수 취소")
			return False
		
		# [Math Engine] 기대 승률에 따른 비중 조절 (0.5배 ~ 1.5배)
		# 기준 승률(min_prob) 이상일 때, 추가 승률 1%당 5% 비중 확대
		math_weight = 1.0 + (win_prob - min_prob) * 5.0
		math_weight = max(0.8, min(1.5, math_weight)) # 너무 급격한 축소는 방지 (최소 0.8배)
		logger.info(f"⚖️ [Math Weight] 기대 승률 가중치 적용: {math_weight:.2f}x (승률 {win_prob*100:.1f}%)")
	else:
		logger.info(f"ℹ️ [Math Filter] 표본 수가 부족하여({sample_count}/{min_count}) 가중치 없이 기본 비중 사용")

	# [자산 데이터 정리] 위에서 이미 계산된 balance와 net_asset 사용
	# net_asset = 예수금(deposit_amt) + 주식평가금(stock_val)
	
	# [전략 설정 및 변수 정의]
	capital_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0
	single_strategy = get_setting('single_stock_strategy', 'FIRE') # 전략 로드
	strategy_rate = float(get_setting('single_stock_rate', 1.0)) # 기준 수익률 로드
	split_cnt = int(get_setting('split_buy_cnt', 5)) # 분할 매수 횟수 로드
	target_cnt = float(get_setting('target_stock_count', 5.0)) # 목표 종목 수 로드
	
	# 현재가(호가) 정보 가져오기
	try:
		current_price = int(check_bid(stk_cd, token=token))
	except:
		current_price = 0

	# [Mathematical Factor Snapshot] 학습용 데이터 수집
	factors = {
		'rsi_1m': rsi_1m,
		'rsi_3m': rsi_3m,
		'rsi_diff': (rsi_1m - rsi_3m) if (rsi_1m and rsi_3m) else 0,
		'price': current_price,
		'win_prob': win_prob,
		'sample_count': sample_count,
		'strategy': single_strategy,
		'capital_ratio': capital_ratio
	}
	
	# 시그널 스냅샷 저장 (수학적 학습의 기초 데이터)
	signal_id = log_signal_snapshot_sync(stk_cd, 'BUY_SIGNAL', factors)
	logger.info(f"💾 [Math Context] 시그널 스냅샷 저장 완료 (ID: {signal_id})")
	
	# [Response Manager] 추적 등록
	if response_manager and signal_id and current_price > 0:
		response_manager.add_signal(signal_id, stk_cd, current_price)

	logger.info(f"매매 자금 비율: {capital_ratio*100:.0f}% (순자산: {int(net_asset or 0):,})")
	
	# 종목당 총 배정 금액 (순자산의 설정 비율만큼 사용 * 수학적 가중치)
	# 예를 들어 자산 1000만원, 종목 5개, 비율 50%, 가중치 1.2인 경우
	# ((1000만 * 0.5) / 5) * 1.2 = 120만원이 종목당 할당액
	alloc_per_stock = ((net_asset * capital_ratio) / target_cnt) * math_weight
	
	# [1:1:2:4... 기하급수적 분할 매수 로직 적용]
	# 분할 매수 횟수에 따라 자동으로 가중치를 계산합니다. (1, 1, 2, 4, 8, 16...)
	
	# 1. 가중치 생성 (Rule: 1:1:2:2:4:4...)
	split_cnt_int = int(split_cnt)
	weights = []
	for i in range(split_cnt_int):
		# 2단계마다 2배씩 증가하는 사용자 수열 (1, 1, 2, 2, 4, 4...)
		weight = 2**(i // 2)
		weights.append(weight)
			
	total_weight = sum(weights)
	
	# 2. 누적 목표 비율 계산
	cumulative_ratios = []
	current_sum = 0
	for w in weights:
		current_sum += w
		cumulative_ratios.append(current_sum / total_weight)
		
	# 3. 로직 적용
	one_shot_amt = 0
	is_custom_ratio = True # 이제 항상 커스텀 비율 로직 사용
	logger.info(f"분할 매수 {split_cnt_int}회 설정 -> 가중치 {weights} (비율: {[f'{r*100:.1f}%' for r in cumulative_ratios]}) 적용")

	expense = 0
	msg_reason = ""
    
    # [보정] 현재 매입 금액 계산 (API 지연 감안하여 내부 추적값과 비교, 큰 값 사용)
	accum_amt = accumulated_purchase_amt.get(stk_cd, 0)
	
	cur_eval = 0
	cur_pchs_amt_api = 0
	if current_holding:
		if 'evlu_amt' in current_holding and current_holding['evlu_amt']:
			cur_eval = int(current_holding['evlu_amt'])
		
		# 매입금액 추정
		if 'pchs_avg_pric' in current_holding and 'rmnd_qty' in current_holding:
			try:
				pchs_avg = float(current_holding['pchs_avg_pric'])
				qty = int(current_holding['rmnd_qty'])
				cur_pchs_amt_api = pchs_avg * qty
			except:
				cur_pchs_amt_api = cur_eval
		else:
			cur_pchs_amt_api = cur_eval
            
	# 내부 추적값과 API 값 중 큰 것을 현재 매입금액으로 사용 (방어적)
	cur_pchs_amt = max(cur_pchs_amt_api, accum_amt)
	if cur_pchs_amt > cur_pchs_amt_api:
		logger.info(f"[데이터 보정] {stk_cd}: API 매입금액({cur_pchs_amt_api}) < 내부 추적금액({accum_amt}) -> 내부 데이터 사용")

	# 보유 여부 판단: API상 있거나, 내부적으로 샀다고 기록되어 있으면 보유 중으로 처리
	is_holding = (current_holding is not None) or (cur_pchs_amt > 0)

	if not is_holding:
		# [신규 진입]
		# 보유 종목 수 체크 (목표 종목 수 초과 방지)
		if my_stocks_count >= target_cnt:
			logger.info(f"[매수 스킵] {stk_cd}: 보유 종목 수({my_stocks_count}개)가 목표({int(target_cnt)}개)에 도달하여 신규 매수 금지")
			return False

		# [신규] 초기 매수 비율 설정 로드 (기본 10%)
		initial_buy_ratio = float(get_setting('initial_buy_ratio', 10.0)) / 100.0
		logger.info(f"[초기 매수] {stk_cd}: 초기 매수 비율 {initial_buy_ratio*100:.1f}% 적용")
		
		# 1차 매수 비율 적용 (초기 매수 비율 반영)
		target_ratio_1st = cumulative_ratios[0] * initial_buy_ratio
		one_shot_amt = alloc_per_stock * target_ratio_1st
		
		# [수정] 최소 매수 금액 보장 (고가 주식도 매수 가능하도록)
		# 1차 매수 금액이 너무 작으면 최소 5만원으로 상향 조정
		MIN_PURCHASE_AMOUNT = 50000
		if one_shot_amt < MIN_PURCHASE_AMOUNT:
			logger.info(f"[자금 조정] 1차 매수액({one_shot_amt:,.0f}원)이 최소 기준({MIN_PURCHASE_AMOUNT:,.0f}원) 미만 → 상향 조정")
			one_shot_amt = MIN_PURCHASE_AMOUNT
		
		# [중요] 예수금 부족 시 매수 방어 로직 (신규 진입 시)
		if balance < (one_shot_amt * 0.5):
			logger.warning(f"[매수 스킵] 예수금 부족 ({balance:,.0f}원 < 목표액 {one_shot_amt:,.0f}원의 50%) - 자산 대비 예수금이 적습니다.")
			return False

		expense = one_shot_amt
		msg_reason = f"신규 매수 (초기 {initial_buy_ratio*100:.0f}%)"
		logger.info(f"[{msg_reason}] {stk_cd}: 매수 진행 (목표: {one_shot_amt:,.0f}원, 전체 할당(가중): {alloc_per_stock:,.0f}원)")

	else:
		# [기보유 종목 처리]
		
		# [원칙 적용] 몰빵/분산 관계없이 추가 매수 조건을 체크합니다.
		# 기존의 '분산 투자 시 추가 매수 금지' 로직은 제거되었습니다.
			
		# [추가 매수 - 불타기/물타기/분할]
		# 현재 평가금액 확인
		cur_eval = 0
		cur_pchs_amt = 0 # 매입금액 (원금)
		if 'evlu_amt' in current_holding and current_holding['evlu_amt']:
			cur_eval = int(current_holding['evlu_amt'])
			
		# 매입금액 추정 (수익률 역산 또는 API 필드 사용)
		# pchs_avg_pric(매입가) * rmnd_qty(보유수량) 사용이 가장 정확
		if 'pchs_avg_pric' in current_holding and 'rmnd_qty' in current_holding:
			try:
				pchs_avg = float(current_holding['pchs_avg_pric'])
				qty = int(current_holding['rmnd_qty'])
				cur_pchs_amt = pchs_avg * qty
			except:
				cur_pchs_amt = cur_eval # fallback
		else:
			cur_pchs_amt = cur_eval # fallback
		
		# 수익률 확인
		pl_rt = float(current_holding.get('pl_rt', 0))
		
		# 현재 매입 비율
		filled_ratio = cur_pchs_amt / alloc_per_stock
		
		# [단계 판독 로직 정밀화] 1:1:2:2:4 수열에 따른 실제 투입액 기준
		actual_current_step = 0
		for i, threshold in enumerate(cumulative_ratios):
			# 실제 투입된 돈이 목표 비중의 90% 이상이면 해당 단계 인정
			if cur_pchs_amt >= (alloc_per_stock * threshold * 0.90):
				actual_current_step = i + 1
		
		# UI 표시용 단계 (최대 split_cnt로 제한)
		display_step = actual_current_step if actual_current_step <= split_cnt else split_cnt
		
		# 2. 손실액 기반 목표 단계 결정 (단위 손실액 420원 원리)
		strategy_rate_val = float(get_setting('single_stock_rate', 1.5))
		total_target_loss = alloc_per_stock * (strategy_rate_val / 100.0)
		unit_loss_trigger = total_target_loss / split_cnt
		
		evlu_pnl = 0
		if current_holding:
			for field in ['evlu_pnl', 'evpnl_amt', 'pnl_amt', 'pchs_pnl_amt']:
				if field in current_holding and current_holding[field]:
					try:
						evlu_pnl = float(current_holding[field])
						if evlu_pnl != 0: break
					except: continue
			if evlu_pnl == 0:
				try:
					cur_prc = float(current_holding.get('cur_prc', 0))
					pchs_avg = float(current_holding.get('pchs_avg_pric', 0))
					qty = int(current_holding.get('rmnd_qty', 0))
					if cur_prc > 0 and pchs_avg > 0 and qty > 0:
						evlu_pnl = (cur_prc - pchs_avg) * qty
				except: pass

		current_loss_amt = abs(evlu_pnl) if evlu_pnl < 0 else 0
		if current_loss_amt == 0 and pl_rt < 0:
			current_loss_amt = abs(cur_pchs_amt * (abs(pl_rt) / 100.0))
		
		# 손실액 비례 목표 단계
		target_step_by_amt = int(current_loss_amt / unit_loss_trigger) if unit_loss_trigger > 0 else 0
		if target_step_by_amt >= split_cnt: target_step_by_amt = split_cnt - 1
		
		# 3. 추가 매수 결정
		target_ratio_val = 0
		next_step_idx = 0
		
		if actual_current_step <= target_step_by_amt:
			next_step_idx = target_step_by_amt
			target_ratio_val = cumulative_ratios[next_step_idx]
		
		target_amt = alloc_per_stock * target_ratio_val
		one_shot_amt = target_amt - cur_pchs_amt
		if one_shot_amt < 0: one_shot_amt = 0
		
		# [Log] 사용자 원칙 기반 투명한 수치 공개
		logger.info(f"📊 [WATER 분석] {stk_cd}:")
		logger.info(f"   - 종목할당액(70%준수): {int(alloc_per_stock):,}원")
		logger.info(f"   - 실제투입단계: {display_step}/{int(split_cnt)} (투입액:{int(cur_pchs_amt):,}원)")
		logger.info(f"   - 손실기준단계: {target_step_by_amt+1}/{int(split_cnt)} (현재손실:{int(current_loss_amt):,}원 / 단위트리거:{int(unit_loss_trigger):,}원)")
		
		# 5. 매수 금액 산출
		target_amt = alloc_per_stock * target_ratio_val
		one_shot_amt = target_amt - cur_pchs_amt
		if one_shot_amt < 0: one_shot_amt = 0
		
		# [Log] 금액 기반 판단 근거 기록
		logger.info(f"📊 [금액기준 판독] {stk_cd}: 현재손실 {int(current_loss_amt):,}원 (트리거:{int(unit_loss_trigger)}원) -> 목표단계:{target_step_by_amt+1}/{int(split_cnt)}")
		
		if one_shot_amt > 0 and one_shot_amt < 50000:
			logger.info(f"[자금 조정] 추가 매수액({one_shot_amt:,.0f}원) 최소 기준 미달 → 5만원 조정")
			one_shot_amt = 50000

		if filled_ratio >= 0.98:
			logger.info(f"[매수 스킬] {stk_cd}: 이미 목표 비중({filled_ratio*100:.1f}%) 도달")
			return False

		# [안전장치] 현재 매도 조건(익절/손절/트레일링)을 만족하는지 확인
		# 만약 지금 팔아야 하는 종목이라면, 아무리 물타기 조건이라도 사면 안 됨
		try:
			tp_rate = float(get_setting('take_profit_rate', 10.0))
			sl_rate = float(get_setting('stop_loss_rate', -10.0))
			
			if pl_rt >= tp_rate:
				logger.warning(f"[매수 금지] {stk_cd}: 현재 익절 구간({pl_rt}%)입니다. 매도 대기 중이므로 추가 매수 불가.")
				return False
			if pl_rt <= sl_rate:
				# WATER 전략이라도 비중이 어느정도 찼을 수 있으니 보수적으로 접근
				if filled_ratio > 0.5:
					logger.warning(f"[매수 금지] {stk_cd}: 현재 손절 구간({pl_rt}%)이며 비중도 50% 이상입니다. 추가 매수 중단.")
					return False
		except: pass

		# [중요] 추가 매수 시에도 예수금 부족 시 매수 방어
		if balance < (one_shot_amt * 0.5):
			logger.warning(f"[매수 스킵] 예수금 부족 ({balance:,.0f}원 < 목표액 {one_shot_amt:,.0f}원의 50%)")
			return False
			
		# [최종 매수 여부 결정] 
		# 위에서 금액 기반으로 계산된 one_shot_amt가 있으면 매수 진행
		should_buy = False
		msg_prefix = ""
		
		if one_shot_amt > 10000: # 최소 1만원 이상일 때만
			should_buy = True
			tag = "물타기" if evlu_pnl < 0 else "불타기"
			msg_prefix = f"{tag}(목표단계:{target_step_by_amt+1})"
		else:
			# 매수 조건 미달 시 관망 로그 (이미 위에서 판독 로그가 찍혔으므로 필요시만 추가)
			pass

		if should_buy:
			expense = one_shot_amt
			
			# [Time-Cut Display] 보유 시간 정보 추가
			elapsed_txt = ""
			if held_since and stk_cd in held_since:
				mins = (time.time() - held_since[stk_cd]) / 60
				elapsed_txt = f"[Time: {mins:.0f}분] "
				msg_prefix = elapsed_txt + msg_prefix

			# 남은 배정 금액 한도 체크

			remaining_alloc = alloc_per_stock - cur_pchs_amt # 매입금액 기준 잔여 한도
			
			# 남은 한도가 1회 매수액보다 적더라도, 최소한의 금액(예: 10만원) 이상이면 매수 시도
			# 하지만 여기서는 간단하게 남은 한도만큼만 매수하도록 설정
			if expense > remaining_alloc:
				expense = remaining_alloc
				logger.info(f"매수 금액 조정: 잔여 한도({remaining_alloc:,.0f}원) 적용")
				
			if msg_reason and "차" in msg_reason: # 위에서 설정한 단계 정보 활용
				msg_prefix = f"{msg_prefix}:{msg_reason}" 
				
			msg_reason = msg_prefix
			logger.info(f"[{msg_reason}] {stk_cd}: 추가 매수 (현재: {cur_eval:,.0f}원 -> 추가: {expense:,.0f}원)")
		else:
			return False

	# 4. 현금 한도 체크 (가진 돈 내에서만)
	if expense > balance:
		logger.warning(f"목표 매수액({expense:,.0f}원) > 주문가능현금({balance:,.0f}원) -> 현금 전액 사용")
		expense = balance
	
	# 최종 점검: 너무 소액인 경우 매수 스킵 (예: 1만원 미만)
	if expense < 10000:
         # 단, 잔고가 거의 0에 수렴하는 경우는 위에서 걸러졌을 것이고, 
         # 여기서 걸리는 건 배정 한도가 꽉 찼거나 하는 경우임.
		logger.warning(f"[매수 스킵] 최종 매출액({expense:,.0f}원)이 너무 적습니다.")
		return False

	logger.info(f"💰 최종 매수 결정액: {expense:,.0f}원 ({msg_reason}, 자산:{net_asset:,.0f}/종목수:{target_cnt})")
	
	# [Cooldown Update] 시도 자체를 기록하여 연속 실패 방지
	last_buy_times[stk_cd] = time.time()

	# time.sleep(0.3)
	
	try:
		bid = int(check_bid(stk_cd, token=token))
	except Exception as e:
		logger.error(f"호가 조회 중 오류 발생: {e}")
		return False # return -> return
	# time.sleep(0.3)

	if bid > 0:
		ord_qty = int(expense // bid)  # 내림하여 정수로 변환
		# [Bug Fix] 매수 금액이 주당 가격보다 적으면 0주가 되어 매수가 안 됨 -> 최소 1주 매수
		if ord_qty == 0 and expense > 0:
			logger.info(f"[수량 보정] {stk_cd}: 목표액({expense:,.0f}원)이 단가({bid:,.0f}원)보다 작음 -> 최소 1주 매수 시도")
			ord_qty = 1
		
		if ord_qty == 0:
			logger.warning(f"주문할 주식 수량이 0입니다. (단가: {bid:,}원)")
			return False
		logger.info(f'주문할 주식 수량: {ord_qty}주 (단가: {bid:,}원)')
	else:
		logger.error(f"호가가 0 이하입니다: {bid}")
		return False


	# 5. 매수 진행
	try:
		return_code, return_msg = buy_stock(stk_cd, ord_qty, bid, token=token)
		
		# [중요 수정] return_code가 "0" (Real API) 또는 "SUCCESS" (Mock API) 모두 처리
		if str(return_code) not in ['0', 'SUCCESS']:
			logger.error(f"주문 실패: {return_msg} (Code: {return_code})")
			return False
		else:
			logger.info(f"주문 성공 확인 (Code: {return_code})")
			
	except Exception as e:
		logger.error(f"주문 중 오류 발생: {e}")
		return False

	# 주문 성공 시점
	
	# 종목명 조회 (DB에서 직접 조회하여 안정성 향상)
	try:
		from database_helpers import get_db_connection
		with get_db_connection() as conn:
			cursor = conn.execute('SELECT name FROM mock_stocks WHERE code = ?', (stk_cd,))
			row = cursor.fetchone()
			stock_name = row['name'] if row else stk_cd
	except Exception as e:
		logger.error(f"종목명 DB 조회 중 오류: {e}")
		stock_name = stk_cd  # 조회 실패 시 코드로 대체

	message = f'{stock_name} {ord_qty}주 매수 주문 전송 완료'
	logger.info(message)
	
	try:
		tel_send(message)
	except Exception as e:
		logger.error(f"텔레그램 전송 중 오류: {e}")
		
	# 쿨타임 업데이트
	last_buy_times[stk_cd] = time.time()
	
	# [추가] 내부 누적 매수 금액 업데이트 (API 반영 지연 대응)
	if stk_cd not in accumulated_purchase_amt:
		accumulated_purchase_amt[stk_cd] = 0
	accumulated_purchase_amt[stk_cd] += expense
	logger.info(f"[데이터 업데이트] {stk_cd}: 내부 누적 매수금 업데이트 (+{expense:,.0f}원 -> 총 {accumulated_purchase_amt[stk_cd]:,.0f}원)")

	# [매매 로그 DB 저장]
	try:
		from database_trading_log import log_buy_to_db
		from kiwoom_adapter import get_current_api_mode
		mode = get_current_api_mode().upper()  # "Mock" -> "MOCK"
		log_buy_to_db(stk_cd, stock_name, ord_qty, bid, mode)
	except Exception as e:
		logger.error(f"매수 로그 DB 저장 실패: {e}")

	# 주문이 성공했으므로 무조건 True 반환
	return True

def reset_accumulation(stk_cd):
	"""외부(매도 로직)에서 매도 확정 시 내부 누적 데이터를 초기화기 위해 호출"""
	global accumulated_purchase_amt
	if stk_cd in accumulated_purchase_amt:
		try:
			del accumulated_purchase_amt[stk_cd]
			logger.info(f"[Reset] {stk_cd}: 매도 확인되어 누적 매수금 데이터 초기화")
		except: pass

def reset_accumulation_global():
	"""모든 종목의 누적 매수 금액 데이터를 초기화합니다."""
	global accumulated_purchase_amt
	accumulated_purchase_amt.clear()
	logger.info("내부 누적 매수 금액 데이터(accumulated_purchase_amt)가 초기화되었습니다.")

if __name__ == '__main__':
	chk_n_buy('005930', token=get_token())