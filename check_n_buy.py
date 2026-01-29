import time
import math
import json
import datetime
import threading # [Lock] 동시성 제어 추가
from kiwoom_adapter import fn_kt00001, fn_ka10004, fn_kt10000, fn_kt00004, get_total_eval_amt, get_current_api_mode
from tel_send import tel_send
from get_setting import get_setting
from logger import logger
from analyze_tools import calculate_rsi, get_rsi_for_timeframe
from database import get_price_history_sync, log_signal_snapshot_sync, get_watering_step_count_sync

from technical_judge import technical_judge
from utils import normalize_stock_code
from candle_manager import candle_manager
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

# [Lock] 종목별 잠금 객체
_stock_locks = {}
_locks_mutex = threading.Lock()

# 매수 체크 함수 (Core Logic)
def _chk_n_buy_core(stk_cd, token, current_holdings=None, current_balance_data=None, held_since=None, outstanding_orders=None, response_manager=None, realtime_data=None, source='검색식', ai_score=0, ai_reason=''):
	global accumulated_purchase_amt # 전역 변수 사용
	global last_sold_times # 매도 시간 추적용
	
	source_tag = f"[{source}]"
	if source == '모델':
		source_tag = f"[🤖AI추천 {ai_score}점]"
	else:
		source_tag = f"[{source}]"
		
	logger.info(f'{source_tag} [매수 체크] 종목 코드: {stk_cd}')
	
	rsi_1m = None
	rsi_3m = None
	
	# [쿨타임 체크] 같은 종목을 너무 자주 매수하는 것을 방지
	# [안정성 개선] 5초 -> 60초로 증가 (과도한 매수 방지)
	# [수정] 이미 보유 중인 종목(물타기)은 쿨타임 무시 (긴급 대응)
	is_held = False
	if current_holdings:
		for s in current_holdings:
			c = s.get('stk_cd', '').replace('A', '')
			if c == stk_cd:
				qty = int(float(str(s.get('rmnd_qty', s.get('hold_qty', '0'))).replace(',', '')))
				if qty > 0:
					is_held = True
					break
	
	buy_cooldown = 60 # 60초 (재진입 방지)
	last_time = last_buy_times.get(stk_cd, 0)
	
	# 보유 중이지 않은 신규 진입 종목만 쿨타임 적용
	if not is_held and (time.time() - last_time < buy_cooldown):
		logger.info(f"[매수 스킵] {stk_cd}: 매수 쿨타임 중 ({int(buy_cooldown - (time.time() - last_time))}초 남음)")
		return False
	elif is_held:
		# logger.info(f"[쿨타임 무시] {stk_cd}: 보유 중(물타기)이므로 즉시 매수 가능")
		pass

	# [재매수 방지] 최근 매도한 종목은 일정 시간 동안 재매수 금지
	# [안정성 개선] 30초 -> 60초로 증가 (API 반영 지연 대응)
	sell_wait = int(get_setting('sell_rebuy_wait_seconds', 60)) # 초 단위 직접 사용
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

	# [안정성 개선] stocks_being_sold 유령 종목 매 루프 정리 (5% 확률 -> 100%)
	if True:  # 매번 정리
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
		
		# 1. 미체결 주문 확인
		if outstanding_orders:
			for order in outstanding_orders:
				order_code = normalize_stock_code(order.get('stk_cd', order.get('code', '')))
				order_type = order.get('type', order.get('ord_tp', ''))
				
				if order_code == stk_cd:
					if order_type == 'sell' or order_type == '02':
						logger.warning(f"🚫 [매수 실패] {stk_cd}: 미체결 매도 주문 존재 -> 매수 차단")
						return False
					
					if order_type == 'buy' or order_type == '01':
						pending_qty = order.get('qty', 0)
						logger.info(f"ℹ️ [물타기 누적] {stk_cd}: 미체결 매수 {pending_qty}주 존재 -> 추가 매수 진행")

		# 2. 쿨타임 체크
		buy_cooldown = 60
		last_time = last_buy_times.get(stk_cd, 0)
		if not is_held and (time.time() - last_time < buy_cooldown):
			remain = int(buy_cooldown - (time.time() - last_time))
			logger.warning(f"🚫 [매수 실패] {stk_cd}: 매수 쿨타임 중 ({remain}초 남음) -> 스킵")
			return False
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
	
	# [API 오류 방어] API 잔고 외에 DB상 오늘 매수 후 보유 중인 종목도 합산하여 카운트 (Double Buy 방지)
	# current_holdings(API) + DB(Today Net Buy > 0)
	api_held_codes = set()
	if current_holdings:
		for stock in current_holdings:
			api_held_codes.add(normalize_stock_code(stock['stk_cd']))
	
	try:
		from database_helpers import get_db_connection
		import datetime
		today_str = datetime.date.today().strftime('%Y-%m-%d')
		
		# [Mode Fix] 현재 API 모드에 맞는 기록만 조회
		current_mode = get_current_api_mode().upper()
		
		# DB에서 오늘 순매수(매수-매도 > 0)인 종목들 조회
		# (단, API 잔고에 이미 있는 건 제외)
		with get_db_connection() as conn:
			rows = conn.execute(
				"SELECT code, type, qty FROM trades WHERE mode = ? AND timestamp LIKE ?", 
				(current_mode, f"{today_str}%",)
			).fetchall()
			
			db_calc_holdings = {}
			for r in rows:
				c, t, q = r['code'], r['type'], r['qty']
				if c not in db_calc_holdings: db_calc_holdings[c] = 0
				if t == 'buy': db_calc_holdings[c] += q
				elif t == 'sell': db_calc_holdings[c] -= q
			
			# 순보유량이 양수인 종목 중 API 잔고에 없는 것 발견 시 추가
			for c, qty in db_calc_holdings.items():
				if qty > 0 and c not in api_held_codes:
					logger.warning(f"[Deep Count] API엔 없으나 DB상 보유 중: {c} ({qty}주) -> 카운트 포함")
					api_held_codes.add(c)
					
					# 만약 현재 매수하려는 종목이 여기에 해당하면 current_holding 복구
					if c == stk_cd and current_holding is None:
						current_holding = {
							'stk_cd': stk_cd,
							'stk_nm': stk_cd,
							'rmnd_qty': qty,
							'pl_rt': 0.0, 
							'cur_prc': 0,
							'pchs_avg_pric': 0,
							'evlu_amt': 0
						}
						logger.info(f"[Deep Count] {stk_cd}: DB 데이터로 보유 상태 복구 완료")

	except Exception as e:
		logger.error(f"[Deep Count 실패] {e}")

	# 최종 보유 종목 수 업데이트
	my_stocks_count = len(api_held_codes)

	# [Memory Cache 방어] API와 DB 모두 실패해도, 봇 실행 중 매수했던 기록이 있으면 차단


	# 설정값 미리 로드
	target_cnt = float(get_setting('target_stock_count', 5))
	if target_cnt < 1: target_cnt = 1
	# target_cnt = 20 # [REMOVED] 사장님 요청에 따라 하드코딩 제거 (DB 설정값 5개 준수)
	
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
			logger.warning(f"[종목수 제한] {stk_cd}: 현재 {my_stocks_count}개 보유 중 (목표: {int(target_cnt)}개) - 신규 매수 불가 (Deep Count)")
			return False
		logger.info(f"[신규 매수 가능] {stk_cd}: 현재 {my_stocks_count}개 보유 중 (목표: {int(target_cnt)}개)")
		
	# time.sleep(0.3)
	
	try:
		# 2. 자산 조회: 순자산(예수금+주식) 기준
		# [최적화] 외부에서 주입받은 경우 재사용 (키 매핑 보정)
		if current_balance_data:
			# bot.py에서 넘겨주는 key는 'deposit'임
			balance = int(current_balance_data.get('deposit', 0))
			# 혹은 'balance'로 올 수도 있으니 체크
			if balance == 0: 
				balance = int(current_balance_data.get('balance', 0))
				
			deposit_amt = balance
			# 'net_asset' or 'total_asset'
			if 'total_asset' in current_balance_data:
				net_asset = int(current_balance_data.get('total_asset', 0))
			else:
				net_asset = int(current_balance_data.get('net_asset', 0))
				
			# [추가] 매입원금(Principal) 기반 자산 계산을 위해 total_pur_amt 확보
			# current_balance_data에 'total_pur_amt'가 있으면 사용, 없으면 net_asset에서 평가손익 제외 시도
			total_pur_amt = int(current_balance_data.get('total_pur_amt', 0))
			if total_pur_amt == 0 and current_holdings:
				for s in current_holdings:
					try:
						total_pur_amt += float(s.get('pchs_avg_pric', 0)) * int(s.get('rmnd_qty', 0))
					except: pass
			
			stock_val = net_asset - balance
		else:
			balance, _, deposit_amt = get_balance(token=token)
			stock_val = get_total_eval_amt(token=token)
			net_asset = deposit_amt + stock_val
			
			# API에서 상세 평가 현황 가져오기 (매입원금 합산용)
			total_pur_amt = 0
			if current_holdings:
				for s in current_holdings:
					try:
						total_pur_amt += float(s.get('pchs_avg_pric', 0)) * int(s.get('rmnd_qty', 0))
					except: pass

		# [Stable Basis] 유저 요청: 손익률에 따라 단계가 변하지 않도록 '원금' 기준 자산 정의
		# basis_asset: 실제 투자된 원금 + 남은 예수금 (미실현 손익 제외)
		basis_asset = deposit_amt + total_pur_amt
		if basis_asset <= 0: basis_asset = net_asset # Fallback
				
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
	
	# [대원칙] RSI는 적용하지 않는다 (나중에 적용 가능하도록 로직은 유지하되, 기본 OFF 권장)
	use_rsi = get_setting('use_rsi_filter', False)
	if use_rsi:
		logger.info("📡 [LASTTRADE RSI] 필터링 활성화 상태 (대원칙에 따라 사용 시 주의)")
		# [Danta] 1분봉 및 3분봉 RSI 동시 체크
		from analyze_tools import get_rsi_for_timeframe as get_rsi
		rsi_1m = get_rsi(stk_cd, '1m')
		rsi_3m = get_rsi(stk_cd, '3m')
		
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
	rsi_diff = (rsi_1m - rsi_3m) if (rsi_1m is not None and rsi_3m is not None) else 0
	win_prob, sample_count = get_win_probability(rsi_1m, rsi_diff)
	
	# 설정값 로드
	min_prob = float(get_setting('math_min_win_rate', 0.55)) # 최소 승률 55%
	min_count = int(get_setting('math_min_sample_count', 5))  # 최소 표본 5건
	
	# [Fix] rsi_1m 또는 win_prob가 None인 경우를 위한 안전한 포맷팅
	rsi_fmt = f"{rsi_1m:.2f}" if rsi_1m is not None else "N/A"
	prob_fmt = f"{win_prob*100:.1f}" if win_prob is not None else "N/A"
	logger.info(f"📊 [LASTTRADE Math] RSI_1m: {rsi_fmt} -> 기대 승률: {prob_fmt}% (표본: {sample_count}건)")
	
	# [Math Engine] 기대 승률에 따른 기본 비중 조절 (0.5배 ~ 1.5배)
	math_weight = 1.0
	if sample_count >= min_count and win_prob is not None:
		if win_prob < min_prob:
			logger.warning(f"📉 [Math Filter] {stk_cd}: 기대 승률({win_prob*100:.1f}%)이 기준({min_prob*100:.0f}%) 미달하여 매수 취소")
			return False
		
		# 기준 승률(min_prob) 이상일 때, 추가 승률 1%당 5% 비중 확대
		math_weight = 1.0 + (win_prob - min_prob) * 5.0
		
	# [New] 60분봉 컨텍스트 추가 (숲의 흐름)
	ctx_60m = {}
	try:
		ctx_60m = candle_manager.get_context_60m(stk_cd)
		logger.info(f"🌳 [60m Context] Trend: {ctx_60m.get('trend_60m')}, MA_Gap: {ctx_60m.get('ma_gap_60m')}%")
	except Exception as e:
		logger.warning(f"⚠️ 60분봉 컨텍스트 획득 실패: {e}")

	# [AI Weight Tuning] 학습된 추세별 가중치(60분봉) 반영 (사용자 요청: 비중 조절 관여)
	try:
		from database_helpers import get_db_connection
		with get_db_connection() as conn:
			cursor = conn.execute("SELECT key, value FROM learned_weights")
			db_weights = {r['key']: r['value'] for r in cursor.fetchall()}
			
			avg_win = db_weights.get('win_rate_weight', 0.5)
			trend_60 = ctx_60m.get('trend_60m', 0)
			
			if trend_60 == 1: # 정배열
				specific_win = db_weights.get('bull_trend_bonus', avg_win)
				multiplier = (specific_win / avg_win) if avg_win > 0 else 1.0
				math_weight *= multiplier
				logger.info(f"🌳 [AI Size] 60m 정배열 보정: {multiplier:.2f}x (승률 {specific_win*100:.1f}%)")
			elif trend_60 == -1: # 역배열
				specific_win = db_weights.get('bear_trend_penalty', avg_win)
				multiplier = (specific_win / avg_win) if avg_win > 0 else 1.0
				math_weight *= multiplier
				logger.info(f"📉 [AI Size] 60m 역배열 보정: {multiplier:.2f}x (승률 {specific_win*100:.1f}%)")
				
		# 최종 가중치 범위 제한 (0.5 ~ 1.5배)
		math_weight = max(0.5, min(1.5, math_weight))
		logger.info(f"⚖️ [Final AI Weight] 최종 매수 비중 가중치: {math_weight:.2f}x")
	except Exception as e:
		logger.warning(f"⚠️ AI 비중 보정 실패: {e}")
		math_weight = max(0.8, min(1.2, math_weight)) # 오류 시 보수적 범위 적용

	# [자산 데이터 정리] 위에서 이미 계산된 balance와 net_asset 사용
	# net_asset = 예수금(deposit_amt) + 주식평가금(stock_val)
	
	# [전략 설정 및 변수 정의]
	capital_ratio = float(get_setting('trading_capital_ratio', 70)) / 100.0
	single_strategy = get_setting('single_stock_strategy', 'WATER') # 전략 로드
	strategy_rate = float(get_setting('single_stock_rate', 4.0)) # 기준 수익률 로드
	split_cnt = int(get_setting('split_buy_cnt', 5)) # 분할 매수 횟수 로드
	target_cnt = float(get_setting('target_stock_count', 1.0)) # 목표 종목 수 로드
	
	# 현재가(호가) 정보 가져오기
	try:
		current_price = int(check_bid(stk_cd, token=token))
	except:
		current_price = 0

	# [Mathematical Factor Snapshot] 학습용 데이터 수집
	factors = {
		'rsi_1m': rsi_1m,
		'rsi_3m': rsi_3m,
		'rsi_diff': rsi_diff,
		'price': current_price,
		'win_prob': win_prob,
		'sample_count': sample_count,
		'strategy': single_strategy,
		'capital_ratio': capital_ratio
	}
	
	# [AI Awareness] 설정창의 주요 팩터들 포함 (사용자 요청: AI가 현재 설정을 항상 파악하도록 함)
	try:
		trading_settings = {
			'set_tp': float(get_setting('take_profit_rate', 10.0)),
			'set_sl': float(get_setting('stop_loss_rate', -10.0)),
			'set_tc_min': int(get_setting('time_cut_minutes', 5)),
			'set_tc_profit': float(get_setting('time_cut_profit', 0.5)),
			'set_target_cnt': target_cnt,
			'set_strategy_rate': strategy_rate,
			'set_split_cnt': split_cnt,
			'set_set_early_stop': int(get_setting('early_stop_step', split_cnt - 1)),
			'set_ts_active': get_setting('use_trailing_stop', False),
			'set_ts_goal': float(get_setting('trailing_stop_activation_rate', 1.5)),
			'set_ts_callback': float(get_setting('trailing_stop_callback_rate', 0.5))
		}
		factors.update(trading_settings)
		factors.update(ctx_60m)
	except Exception as e:
		logger.warning(f"⚠️ 설정 팩터 수집 실패: {e}")
	
	# 실시간 정보 추가 (거래량, 체결강도 등)
	if realtime_data:
		factors.update(realtime_data)
	
	# 시그널 스냅샷 저장 (수학적 학습의 기초 데이터)
	signal_id = log_signal_snapshot_sync(stk_cd, 'BUY_SIGNAL', factors)
	logger.info(f"💾 [Math Context] 시그널 스냅샷 저장 완료 (ID: {signal_id})")
	
	# [Response Manager] 추적 등록
	if response_manager and signal_id and current_price > 0:
		response_manager.add_signal(signal_id, stk_cd, current_price)

	logger.info(f"매매 자금 비율: {capital_ratio*100:.0f}% (순자산: {int(net_asset or 0):,})")
	
	# [수정] 최소 매수 금액 보장 (설정값 연동)
	min_buy_setting = get_setting('min_purchase_amount', 2000)
	try:
		MIN_PURCHASE_AMOUNT = int(str(min_buy_setting).replace(',', ''))
	except:
		MIN_PURCHASE_AMOUNT = 2000

	# 종목당 총 배정 금액 (원금 기준 자산의 설정 비율만큼 사용 * 수학적 가중치)
	# 유저 요청: 손익률/평가금에 따라 단계가 변하지 않도록 basis_asset 사용
	alloc_per_stock = ((basis_asset * capital_ratio) / target_cnt) * math_weight
	
	# [1:1:2:4... 기하급수적 분할 매수 로직 적용]
	# 분할 매수 횟수에 따라 자동으로 가중치를 계산합니다. (1, 1, 2, 4, 8, 16...)
	
	# 1. 가중치 생성 (Rule: 1:1:2:2:4:4...)
	split_cnt_int = int(split_cnt)
	# [New] 조기 손절 단계 고려 (사용자 요청: 조기 손절이 4단계면 4단계 기준으로 비중 계산)
	# 설정이 없으면 관례적으로 전체 단계 - 1을 사용합니다.
	early_stop_step = int(get_setting('early_stop_step', split_cnt_int - 1))
	if early_stop_step <= 0: early_stop_step = split_cnt_int

	weights = []
	for i in range(split_cnt_int):
		# [수정] 사용자 요청에 따라 1:1:2:2:4:4 수열 적용
		weight = 2**(i // 2)
		weights.append(weight)
			
	# [중요] 비중 계산의 분모(Total Weight)를 조기 손절 단계(예: 4차)까지만 합산
	# 이렇게 하면 조기 손절 단계에 도달했을 때 할당 자금의 100%가 투입됩니다.
	total_weight = sum(weights[:early_stop_step])
	if total_weight <= 0: total_weight = sum(weights) # Fallback
	
	# 2. 누적 목표 비율 계산
	cumulative_ratios = []
	current_sum = 0
	for w in weights:
		current_sum += w
		cumulative_ratios.append(current_sum / total_weight)
		
	logger.info(f"분할 매수 {split_cnt_int}회 (기준:{early_stop_step}차) -> 가중치 {weights} (비율: {[f'{r*100:.1f}%' for r in cumulative_ratios]}) 적용")

	expense = 0
	msg_reason = ""
	filled_ratio = 0.0 # [Fix] UnboundLocalError 방지

    
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
	cur_pchs_qty = int(current_holding.get('rmnd_qty', 0)) if current_holding else 0
	
	if cur_pchs_amt > cur_pchs_amt_api:

		logger.info(f"[데이터 보정] {stk_cd}: API 매입금액({cur_pchs_amt_api}) < 내부 추적금액({accum_amt}) -> 내부 데이터 사용")

	# 보유 여부 판단: API상 있거나, 내부적으로 샀다고 기록되어 있으면 보유 중으로 처리
	is_holding = (current_holding is not None) or (cur_pchs_amt > 0)

	if not is_holding:
		# 보유 종목 수 체크 (목표 종목 수 초과 방지)
		if my_stocks_count >= target_cnt:
			logger.info(f"[매수 스킵] {stk_cd}: 보유 종목 수({my_stocks_count}개)가 목표({int(target_cnt)}개)에 도달하여 신규 매수 금지")
			return False

		# [시간 제한 해제] 사용자 요청: 24시간 언제든 매수 허용
		# if not is_mock and datetime.datetime.now().hour >= 15: ... (Removed)

		# [수정] 1:1:2:4:8 비율대로 직접 매수 (initial_buy_ratio 제거)
		# 1단계 = 전체 할당액의 10% (가중치 1/10)
		target_ratio_1st = cumulative_ratios[0]
		one_shot_amt = alloc_per_stock * target_ratio_1st
		logger.info(f"[신규 매수] {stk_cd}: 1단계 비율 {target_ratio_1st*100:.1f}% 적용")
		
		# [수정] 최소 매수 금액 보장
		if one_shot_amt < MIN_PURCHASE_AMOUNT:
			logger.info(f"[자금 조정] 1차 매수액({one_shot_amt:,.0f}원)이 최소 기준({MIN_PURCHASE_AMOUNT:,.0f}원) 미달 → 상향 조정")
			one_shot_amt = MIN_PURCHASE_AMOUNT
		
		# [Heavy Stock Guard] 신규 진입 시, 1주 가격이 배정 금액의 50%를 넘으면 스킵
		# 이유: 1주가 너무 비싸면 분할 매수(물타기)가 불가능하여 전략이 망가짐
		if current_price > (alloc_per_stock * 0.5):
			logger.warning(f"[매수 스킵] {stk_cd}: 종목 단가({current_price:,.0f}원)가 배정액({alloc_per_stock:,.0f}원) 대비 너무 비쌈 (50% 초과) - 분할매수 불가")
			return False

		# [중요] 예수금 부족 시 매수 방어 로직 (신규 진입 시)
		if balance < (one_shot_amt * 0.5):
			logger.warning(f"[매수 스킵] 예수금 부족 ({balance:,.0f}원 < 목표액 {one_shot_amt:,.0f}원의 50%) - 자산 대비 예수금이 적습니다.")
			return False

		expense = one_shot_amt
		
		# [Source Tagging] 사유에 출처 명시 (검색식 vs AI모델)
		msg_reason = "1단계 신규진입"
			
		# [Math Weight] 비중 조절 내역 추가
		if math_weight != 1.0:
			msg_reason += f" (가중치 {math_weight:.2f}x)"
		
		# [AI RSI 필터] 신규 매수 시 (달리는 말에 올라타기: 신고가 40일선 전략 최적화)
		# RSI 50(설정값) 이상인 "강한 힘"이 있는 구간에서만 진입
		try:
			# [Yang-bong Filter] 음봉 진입 금지 (현재가 >= 시가)
			# 사장님 요청: 음봉일 때 진입해서 물리는 상황 방어
			try:
				# API나 실시간 데이터에서 시가(open) 가져오기
				open_price = 0
				if realtime_data and stk_cd in realtime_data:
					open_price = float(realtime_data.get(f"{stk_cd}_open", 0))
				
				# 시가 데이터가 없으면 API에서 다시 확인 시도
				if open_price <= 0:
					# stock_info 등에서 시가 추출 로직 (편의상 시가 정보가 없으면 0으로 처리)
					pass
				
				if open_price > 0 and current_price < open_price:
					logger.warning(f"[음봉 매수 제한] {stk_cd}: 현재가({current_price:,.0f}) < 시가({open_price:,.0f}) -> 음봉이므로 신규 진입 취소")
					return False
			except: pass

			from analyze_tools import get_rsi_for_timeframe
			rsi_1m = get_rsi_for_timeframe(stk_cd, '1m')
			
			# 설정된 매수 RSI 기준값 사용 (기본 50)
			min_rsi_buy = float(get_setting('min_rsi_for_buy', 50.0))
			
			if rsi_1m is not None:
				if rsi_1m < min_rsi_buy:
					logger.info(f"[매수 스킵] 신규 진입 시 모멘텀 부족 (RSI {rsi_1m:.0f} < {min_rsi_buy:.0f}) -> 기준 미달")
					return False
				
				# [New High Strategy] RSI 70 이상 과열 구간 처리 (정찰병 전략)
				# 사장님 지시: 70 이상이면 너무 뜨거우니 비중을 절반으로 줄여서 진입
				if rsi_1m >= 70:
					logger.info(f"[정찰병 진입] RSI 과열({rsi_1m:.0f} >= 70) 구간 -> 상따 리스크 관리 위해 1차 매수금액 50% 축소")
					one_shot_amt *= 0.5
					
					# 최소 금액 재검증
					if one_shot_amt < MIN_PURCHASE_AMOUNT:
						one_shot_amt = MIN_PURCHASE_AMOUNT

		except Exception as e:
			pass
			
		logger.info(f"[{msg_reason}] {stk_cd}: 매수 진행 (목표: {one_shot_amt:,.0f}원, 전체 할당(가중): {alloc_per_stock:,.0f}원)")

	else:
		# [기보유 종목 처리]
		
		# [Safety Logic] 사장님 요청: 1. 손절 후 재진입 쿨타임(3분) & 2. RSI 45 이상 확인 (확실한 반등 시에만 물타기)
		try:
			from database_helpers import get_db_connection
			import datetime
			
			# 1. 최근 매도 시간 확인 (3분 쿨타임)
			# 매도 직후 급하게 다시 사는 '뇌동매매' 방지
			with get_db_connection() as conn:
				last_sell = conn.execute(
					"SELECT timestamp FROM trades WHERE code = ? AND (type='SELL' OR type='sell') ORDER BY id DESC LIMIT 1",
					(stk_cd,)
				).fetchone()
				
				if last_sell:
					last_sell_str = last_sell['timestamp'] # YYYY-MM-DD HH:MM:SS
					# [Fix] 포맷 매칭 (초 단위 없는 경우 대비)
					try:
						last_sell_dt = datetime.datetime.strptime(last_sell_str, '%Y-%m-%d %H:%M:%S')
					except:
						last_sell_dt = datetime.datetime.now() # 에러 시 현재 시간으로 간주하여 안전하게 패스
					
					elapsed_seconds = (datetime.datetime.now() - last_sell_dt).total_seconds()
					
					# 최근 매도가 오늘 일어난 것이고, 설정된 쿨타임(기본 2분/120초) 미만이면 차단
					# (어제 판 건 상관없으므로 하루(86400초) 이내인 경우만 체크)
					# [No Hardcoding] 상수 제거 -> DB 설정값 사용 (기본값 120초)
					cooldown_sec = int(get_setting('rebuy_cooldown_seconds', 120))
					
					if elapsed_seconds < 86400 and elapsed_seconds < cooldown_sec: 
						logger.warning(f"[재진입 금지] {stk_cd}: 최근 매도 후 {elapsed_seconds:.0f}초 경과 ({cooldown_sec}초 쿨타임 중) -> 매수 보류")
						return False

			# 2. RSI 45 확인 (충분한 반등 힘이 있을 때만 추가 매수)
			# 물타기라도 하락 추세(RSI < 45)에서는 하지 않고, 고개를 들 때(RSI >= 45) 한다.
			from analyze_tools import get_rsi_for_timeframe
			rsi_1m_rebuy = get_rsi_for_timeframe(stk_cd, '1m')
			if rsi_1m_rebuy is not None and rsi_1m_rebuy < 45:
				logger.info(f"[추가매수 보류] {stk_cd}: 반등 모멘텀 부족 (RSI {rsi_1m_rebuy:.0f} < 45) -> 45 이상 회복 시 진입")
				return False

		except Exception as e:
			logger.warning(f"[Safety Check Error] 재진입 안전장치 오류(무시하고 진행): {e}")

		# [원칙 적용] 몰빵/분산 관계없이 추가 매수 조건을 체크합니다.
		# 기존의 '분산 투자 시 추가 매수 금지' 로직은 제거되었습니다.
			
	# [추가 매수 - 불타기/물타기/분할]
		# 현재 평가금액 확인
		cur_eval = 0
		cur_pchs_amt = 0 # 매입금액 (원금)
		if 'evlu_amt' in current_holding and current_holding['evlu_amt']:
			cur_eval = int(current_holding['evlu_amt'])
			
		# [중요 수정] 매입금액 정보가 없으면(0원이면) 추가 매수 계산 불가 -> 스킵 (DB방어/메모리방어 시 발생)
		if 'pchs_amt' in current_holding and current_holding['pchs_amt']:
			cur_pchs_amt = float(current_holding['pchs_amt'])
		elif 'pur_amt' in current_holding and current_holding['pur_amt']:
			cur_pchs_amt = float(current_holding['pur_amt'])
			
		if cur_pchs_amt <= 0:
			logger.warning(f"[물타기 스킵] {stk_cd}: 매입금액 정보 없음(0원) - 데이터 불충분하여 추가 매수 중단")
			return False
			
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
		
		# [Safety] 현재가가 0원이면 수익률도 믿을 수 없음 -> 0으로 강제 초기화 (매수 방지)
		try:
			cur_prc_chk = float(str(current_holding.get('cur_prc', '0')).replace(',', ''))
			if cur_prc_chk <= 0:
				pl_rt = 0.0
				logger.warning(f"⚠️ [Data Warning] {stk_cd}: 현재가 0원 -> 수익률 0% 처리 (매수 보류)")
		except: pass
		
		# 현재 매입 비율
		filled_ratio = cur_pchs_amt / alloc_per_stock
		
		# [Step Calc] Transaction Count Method (사용자 요구: 매수 명령 횟수 = 단계)
		buy_mode = "REAL"
		try:
			if str(get_setting('use_mock_server', False)).lower() in ['1', 'true', 'on']: buy_mode = "MOCK"
			elif str(get_setting('is_paper_trading', False)).lower() in ['1', 'true', 'on']: buy_mode = "PAPER"
		except: pass
		
		# [Step Calc] Transaction Count Method (사용자 요구: 매수 명령 횟수 = 단계)
		# DB에서 매수 명령 횟수를 직접 카운트 (DISTINCT timestamp)
		db_step_count = get_watering_step_count_sync(stk_cd, buy_mode)
		
		# [절대 규칙] 1주면 무조건 1차 (DB 기록보다 수량 상태를 우선시하여 꼬임 방지)
		if cur_pchs_qty <= 1:
			actual_current_step = 1
		elif db_step_count > 0:
			actual_current_step = db_step_count
		else:
			# DB 기록이 없으면 비중 기반으로 추정 (Fallback)
			if filled_ratio < 0.08: actual_current_step = 1
			elif filled_ratio < 0.18: actual_current_step = 2
			elif filled_ratio < 0.35: actual_current_step = 3
			elif filled_ratio < 0.70: actual_current_step = 4
			else: actual_current_step = 5
		
		if actual_current_step < 1: actual_current_step = 1
		
		# [UI Sync]
		display_step = actual_current_step if actual_current_step <= split_cnt else split_cnt
		if current_holding:
			current_holding['current_step'] = display_step
			
		logger.info(f"[Step Calc] {stk_cd}: DB기록({db_step_count}회), 비중({filled_ratio*100:.1f}%) -> 최종 {display_step}차 판독 (수량:{cur_pchs_qty}주)")

		# 2. [물타기 목표 설정]
		strategy_rate_val = float(get_setting('single_stock_rate', 4.0))
		if strategy_rate_val <= 0: strategy_rate_val = 4.0
		
		# [수정] 상대적 물타기 판정 (수익률은 단계에 종속됨)
		# 현재 단계(actual_current_step) 평단 대비 설정된 간격(Interval)만큼 하락했는가?
		# 예: -11% 하락 / 5% 간격 = 2단계 점프 -> 현재 1차 + 2 = 3차 목표
		steps_to_jump = int(abs(pl_rt) // strategy_rate_val) if pl_rt < 0 else 0
		theoretical_target_step = actual_current_step + steps_to_jump
		
		if theoretical_target_step > split_cnt: theoretical_target_step = split_cnt
		
		# 목표 단계가 현재 단계보다 높을 때만 진입 (진정한 추가 매수)
		if theoretical_target_step > actual_current_step:
			target_step_by_amt = theoretical_target_step - 1 # 인텍스 기준
			logger.info(f"🚩 [Relative Watering] {stk_cd}: 현재 {actual_current_step}차 (수익률 {pl_rt}%) -> 목표 {theoretical_target_step}차로 이동 결정")
		else:
			target_step_by_amt = -1
			
		# 더미 변수 설정 (로깅용)
		current_loss_amt = 0
		unit_loss_trigger = 0

		# [FIRE 전략 보강] 수익 발생 시 불타기 단계 계산
		if single_strategy == 'FIRE' and pl_rt > 0:
			# FIRE 전략은 '추가매수간격(예: 4%)' 상승 시마다 불타기 수행
			fire_interval = float(get_setting('additional_buy_interval', 4.0)) # 기본 4%
			if fire_interval <= 0: fire_interval = 4.0
			
			# 현재 수익률이 간격의 몇 배인지 계산
			additional_step = int(pl_rt / fire_interval)
			target_step_fire = additional_step
			
			# 불타기 목표 단계 설정
			target_step_by_amt = target_step_fire
			logger.info(f"🔥 [FIRE 분석] 수익률 {pl_rt}% (간격 {fire_interval}%) -> 불타기 목표: {target_step_by_amt+1}차")

		if target_step_by_amt >= split_cnt: target_step_by_amt = split_cnt - 1
		
		# [Critical Fix] 수익률 기반 강력 방어 (금액 로직 무시)
		# 현재 단계(actual_current_step)가 1 이상(보유 중)일 때,
		# 수익률이 다음 단계 트리거(예: -4%, -8%)에 도달하지 않았으면 매수 원천 차단
		if 'WATER' in single_strategy and actual_current_step >= 1:
			# [수정] 평단가 기준 고정 간격 물타기 (항상 -4% 하락 시 추매)
			# 기존: -4% * 단계 (점점 깊어짐) -> 수정: -4% 고정 (평단이 낮아졌으므로 상대적 기준)
			next_target_rate = -1.0 * strategy_rate_val 
			
			# [Debug Check] 물타기 판단 상세 로그
			logger.info(f"🔍 [물타기 정밀판독] {stk_cd}: 현재단계 {actual_current_step}차 | 현재수익 {pl_rt:.2f}% | 목표수익 {next_target_rate:.2f}% | 갭 {pl_rt - next_target_rate:.2f}%")

			# 여유폭(buffer) 0.1% 감안
			if pl_rt > (next_target_rate + 0.1):
				# logger.info(f"[물타기 방어] {stk_cd}: 현재 {pl_rt}% > 목표 {next_target_rate}% (단계:{actual_current_step}) -> 추가 매수 금지")
				return False
				
			# [Bug Fix] 수익률이 목표 구간에 도달했음에도 비중(filled_ratio) 계산상의 문제로 
			# theoretical_target_step이 actual_current_step과 같게 나오는 경우 방지
			if pl_rt <= next_target_rate and theoretical_target_step <= actual_current_step:
				theoretical_target_step = actual_current_step + 1
				logger.info(f"🔄 [Step Force] {stk_cd}: 수익률({pl_rt}%) 기준 강제 단계 상향 ({actual_current_step} -> {theoretical_target_step})")
				
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
		
		# [CRITICAL Fix] 예산 초과 시에도 물타기 조건 충족 시 최소 가중치(예: 2주) 매수 보장
		# 비중 계산상으로는 이미 MAX더라도, 단계(Step)상 다음 단계로 넘어가야 한다면 
		# 해당 단계의 가중치(weights)만큼 살 수 있는 금액을 투입한다.
		if theoretical_target_step > actual_current_step:
			step_weight = weights[theoretical_target_step-1] if theoretical_target_step <= len(weights) else 1
			# 가중치만큼의 수량을 확보하기 위한 최소 금액 계산
			min_step_amt = step_weight * current_price
			
			if one_shot_amt < min_step_amt:
				logger.info(f"⚠️ [Budget Bypass] {stk_cd}: 예산상 금액({one_shot_amt:,.0f}원)이 부족하지만 {theoretical_target_step}차 단계 가중치({step_weight}주) 확보를 위해 {min_step_amt:,.0f}원 투입")
				one_shot_amt = min_step_amt
		
		if one_shot_amt < 0: one_shot_amt = 0
		
		# [Log] 금액 기반 판단 근거 기록
		logger.info(f"📊 [금액기준 판독] {stk_cd}: 현재손실 {int(current_loss_amt):,}원 (트리거:{int(unit_loss_trigger)}원) -> 목표단계:{target_step_by_amt+1}/{int(split_cnt)}")
		
		# [수정] 이미 위에서 정의된 MIN_PURCHASE_AMOUNT 사용
		if one_shot_amt > 0 and one_shot_amt < MIN_PURCHASE_AMOUNT:
			logger.info(f"[자금 조정] 추가 매수액({one_shot_amt:,.0f}원) 최소 기준({MIN_PURCHASE_AMOUNT:,.0f}원) 미달 → {MIN_PURCHASE_AMOUNT:,.0f}원 조정")
			one_shot_amt = MIN_PURCHASE_AMOUNT

		if filled_ratio >= 0.98:
			logger.info(f"[매수 스킬] {stk_cd}: 이미 목표 비중({filled_ratio*100:.1f}%) 도달")
			return False

		# [안전장치] 현재 매도 조건(익절/손절/트레일링)을 만족하는지 확인
		# 만약 지금 팔아야 하는 종목이라면, 아무리 물타기/불타기 조건이라도 사면 안 됨
		try:
			tp_rate = float(get_setting('take_profit_rate', 10.0))
			sl_rate = float(get_setting('stop_loss_rate', -10.0))
			
			if pl_rt >= tp_rate:
				logger.warning(f"[매수 금지] {stk_cd}: 현재 익절 구간({pl_rt}%)입니다. 매도 대기 중이므로 추가 매수 불가.")
				return False
			
			# [수정] 50% 비중 체크 제거 (WATER 전략은 손절 구간에서도 물타기를 수행해야 함)
			if single_strategy != 'FIRE' and pl_rt <= sl_rate:
				# WATER 전략은 MAX 단계 도달 전까지는 비중과 무관하게 물타기 허용
				pass
		except: pass

		# [중요] 추가 매수 시에도 예수금 부족 시 매수 방어
		if balance < (one_shot_amt * 0.5):
			logger.warning(f"[매수 스킵] 예수금 부족 ({balance:,.0f}원 < 목표액 {one_shot_amt:,.0f}원의 50%)")
			return False
			
		# [최종 매수 여부 결정] 
		# 위에서 금액 기반으로 계산된 one_shot_amt가 있으면 매수 진행
		should_buy = False
		msg_prefix = ""
		
		if one_shot_amt >= MIN_PURCHASE_AMOUNT: # 설정된 최소 금액 이상일 때만 매수
			should_buy = True
			tag = "물타기" if pl_rt < 0 else "불타기"
			msg_prefix = f"{tag}(목표단계:{target_step_by_amt+1})"
            
			# [AI RSI 필터] 추가 매수 시 힘(Trend) 확인
			try:
				from analyze_tools import get_rsi_for_timeframe
				rsi_1m = get_rsi_for_timeframe(stk_cd, '1m')
				if rsi_1m is not None:
					is_plus = (pl_rt >= 0)
					if is_plus: # 불타기 (수익 중) -> [사용자 요청] 불타기 금지 (물타기 전용)
						logger.info(f"[매수 스킵] 사용자 요청에 의해 불타기(수익 중 추매) 비활성화")
						should_buy = False
					else: # 물타기 (손실 중)
						# 하락 추세(50 미만)에서는 절대 물타기 금지 (눌림목에서만 허용)
						if rsi_1m < 50:
							logger.info(f"[매수 스킵] 물타기 구간이나 하락 추세 지속 (RSI {rsi_1m:.0f} < 50) -> 죽은 고양이에 물타지 않음")
							should_buy = False
			except Exception as e:
				logger.error(f"RSI 체크 실패(Pass): {e}")
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
			
			# [Source Tagging Bypass] 구분 컬럼이 따로 있으니 사유에서는 제거
			msg_reason = msg_prefix
			if math_weight != 1.0:
				msg_reason += f" ({math_weight:.2f}x)"
				
			logger.info(f"[{msg_reason}] {stk_cd}: 추가 매수 (현재: {cur_eval:,.0f}원 -> 추가: {expense:,.0f}원)")
		else:
			return False

	# 4. 현금 한도 체크 (가진 돈 내에서만)
	if expense > balance:
		logger.warning(f"목표 매수액({expense:,.0f}원) > 주문가능현금({balance:,.0f}원) -> 현금 전액 사용")
		expense = balance
	
	# 최종 점검: 너무 소액인 경우 매수 스킵
	if expense < MIN_PURCHASE_AMOUNT:
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
		# [Bug Fix & 오버 매수 방지]
		if ord_qty == 0 and expense > 0:
			# 이미 비중이 90% 이상 찼는데 1주도 못 살 돈만 남았다면 -> 굳이 무리해서 사지 않고 종료 (오버 매수 방지)
			# 단, 아주 극초기라면 최소 1주는 사야 함
			if filled_ratio >= 0.9:
				logger.warning(f"[오버 매수 방지] {stk_cd}: 목표 비중 임박({filled_ratio*100:.1f}%) -> 잔여금액({expense:,.0f}원)이 1주 가격({bid:,.0f}원)보다 적어 매수 포기")
				return False
			else:
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
		return_code, return_msg = buy_stock(stk_cd, ord_qty, bid, token=token, source=source)
		
		# [중요 수정] return_code가 "0" (Real API) 또는 "SUCCESS" (Mock API) 모두 처리
		if str(return_code) not in ['0', 'SUCCESS']:
			logger.error(f"주문 실패: {return_msg} (Code: {return_code})")
			return False
		else:
			logger.info(f"주문 성공 확인 (Code: {return_code})")
			
			# [Memory Cache] 금일 매수 종목 등록 (중복 진입 방지용)
			# 재시작 전까지 유효하며, 비정상적인 연속 매수를 막아줌
			global today_buy_attempts
			if 'today_buy_attempts' not in globals(): today_buy_attempts = set()
			today_buy_attempts.add(stk_cd)
			
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

	message = f'[{msg_reason}] {stock_name} {ord_qty}주 매수 주문 전송 완료'
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
	# [데이터 업데이트] {stk_cd}: 내부 누적 매수금 업데이트 (+{expense:,.0f}원 -> 총 {accumulated_purchase_amt[stk_cd]:,.0f}원)
	
	# [AI] 분할 매수 수행 시, 해당 종목의 AI 리스크 관리 이력(분할 매도 기록) 초기화
	# 매수가 이루어졌다는 것은 비중이 다시 늘어났음을 의미하므로 AI가 새로운 시점에서 다시 판별하도록 함
	try:
		import check_n_sell
		if stk_cd in check_n_sell.ai_partial_sold_history:
			del check_n_sell.ai_partial_sold_history[stk_cd]
			logger.info(f"🧬 [AI Sync] {stk_cd}: 분할 매수 발생으로 AI 리스크 관리 이력 초기화")
	except: pass
	
	# [Time-Cut] 매수 발생 시 보유 시각을 '현재'로 갱신 (리셋)
	# 물타기를 했다는 것은 새로운 게임의 시작이므로 시간을 벌어줌
	if held_since is not None:
		held_since[stk_cd] = time.time()
		logger.info(f"⏰ [Time Reset] {stk_cd}: 보유 시각 갱신 (매수 발생)")

	# [매매 로그 DB 저장]
	try:
		from database_trading_log import log_buy_to_db
		mode = get_current_api_mode().upper()  # "Mock" -> "MOCK"
		log_buy_to_db(stk_cd, stock_name, ord_qty, bid, mode, msg_reason, source)
	except Exception as e:
		logger.error(f"매수 로그 DB 저장 실패: {e}")

	# 주문이 성공했으므로 무조건 True 반환
	return True

def reset_accumulation(stk_cd):
	"""외부(매도 로직)에서 매도 확정 시 내부 누적 데이터를 초기화기 위해 호출"""
	global accumulated_purchase_amt
	
	# 1. 메모리 초기화
	if stk_cd in accumulated_purchase_amt:
		try:
			del accumulated_purchase_amt[stk_cd]
			logger.info(f"[Reset] {stk_cd}: 매도 확인되어 누적 매수금 데이터(Memory) 초기화")
		except: pass

	# 2. DB 초기화 (중요: 재매수 시 1차부터 시작하도록 trades 테이블 정리)
	try:
		from database_trading_log import delete_stock_trades
		mode = get_current_api_mode().upper()
		delete_stock_trades(stk_cd, mode)
	except Exception as e:
		logger.error(f"[Reset Error] {stk_cd} DB 초기화 실패: {e}")

def reset_accumulation_global():
	"""모든 종목의 누적 매수 금액 데이터를 초기화합니다."""
	global accumulated_purchase_amt
	accumulated_purchase_amt.clear()
	logger.info("내부 누적 매수 금액 데이터(accumulated_purchase_amt)가 초기화되었습니다.")

# [Wrapper] 외부에서 호출하는 함수 (Thread-S# Wrapper 함수 (동시성 제어 적용)
def chk_n_buy(stk_cd, token, current_holdings=None, current_balance_data=None, held_since=None, outstanding_orders=None, response_manager=None, realtime_data=None, source='검색식', ai_score=0, ai_reason=''):
	# [Lock] 종목별 락 생성 및 획득
	global _stock_locks, _locks_mutex
	with _locks_mutex:
		if stk_cd not in _stock_locks: _stock_locks[stk_cd] = threading.Lock()
		lock = _stock_locks[stk_cd]
	
	# Non-blocking 시도 (이미 처리 중이면 스킵)
	if not lock.acquire(blocking=False):
		logger.info(f"[Skip] {stk_cd} 이미 매수 프로세스 진행 중")
		return False
		
	try:
		return _chk_n_buy_core(stk_cd, token, current_holdings, current_balance_data, held_since, outstanding_orders, response_manager, realtime_data, source, ai_score, ai_reason)
	finally:
		lock.release()

if __name__ == '__main__':
	chk_n_buy('005930', token=get_token())