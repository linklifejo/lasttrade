from logger import logger
from utils import log_trading_event
from kiwoom_adapter import get_my_stocks, sell_stock

def sell_all_stocks(token=None):
	"""보유 중인 모든 종목을 시장가로 매도하며, 완벽하게 매도될 때까지 재시도합니다."""
	import time
	from tel_send import tel_send
	
	max_retries = 3  # 최대 재시도 횟수
	retry_count = 0
	total_sold_count = 0
	total_sold_list = []

	while retry_count < max_retries:
		try:
			# 1. 잔고 조회
			my_stocks = get_my_stocks(token=token)
			
			# 2. 잔고 없으면 성공으로 종료
			if not my_stocks:
				if retry_count == 0:
					logger.info("보유 종목이 없습니다.")
					return 0, []
				else:
					logger.info(f"모든 종목 매도 완료 (재시도 {retry_count}회 수행)")
					return total_sold_count, total_sold_list

			# 첫 시도일 때만 알림
			if retry_count == 0:
				total_stocks_count = len(my_stocks)
				tel_send(f"🚨 전량 매도 시작! 총 {total_stocks_count}개 종목을 매도합니다...")
			else:
				tel_send(f"🔄 전량 매도 재시도 ({retry_count}/{max_retries}) - 남은 종목: {len(my_stocks)}개")

			# 3. 각 종목 매도 주문
			current_round_sold = False
			for stock in my_stocks:
				stock_code = stock['stk_cd'].replace('A', '')
				stock_name = stock['stk_nm']
				qty = int(stock['rmnd_qty'])
				
				if qty <= 0:
					continue

				logger.info(f"{stock_name}({stock_code}) {qty}주 매도 시도...")
				
				# 시장가 매도 주문
				return_code, return_msg = sell_stock(stock_code, str(qty), token=token)
				
				# [Fix] SUCCESS 또는 0 모두 성공으로 간주
				if str(return_code) in ['0', 'SUCCESS', '0000', 'OK']:
					current_round_sold = True
					msg = f"✅ {stock_name} {qty}주 매도 주문 완료"
					logger.info(msg)
					tel_send(msg) # 개별 매도 메시지 전송
					
					# 리스트에 없으면 추가 (중복 방지)
					if stock_code not in total_sold_list:
						total_sold_list.append(stock_code)
						total_sold_count += 1
						
						# [Report] 매매 일지 기록
						try:
							# stock 데이터가 API 응답마다 다를 수 있으므로 안전하게 처리
							pl_rt = float(stock.get('pl_rt', 0))
							cur_prc = int(float(stock.get('cur_prc', stock.get('cur_price', 0))))
							log_trading_event("sell", stock_code, stock_name, qty, cur_prc, pl_rt, "전체매도(Manual)")
						except Exception as e:
							logger.error(f"매도 로그 기록 실패: {e}")
				else:
					msg = f"❌ {stock_name} 매도 실패: {return_msg}"
					logger.error(msg)
					
				time.sleep(0.2) # 과도한 API 호출 방지

			# 매도 주문 후 체결 대기 (2초)
			time.sleep(2)
			
			retry_count += 1

		except Exception as e:
			logger.error(f"전량 매도 중 오류 발생: {e}")
			tel_send(f"❌ 전량 매도 중 오류 발생: {e}")
			return total_sold_count, total_sold_list

	# 최대 횟수 초과 시
	logger.warning("최대 재시도 횟수를 초과했습니다. 일부 종목이 매도되지 않았을 수 있습니다.")
	tel_send("⚠️ 최대 재시도 횟수 초과! 일부 종목이 남아있을 수 있으니 잔고를 확인하세요.")
	return total_sold_count, total_sold_list
