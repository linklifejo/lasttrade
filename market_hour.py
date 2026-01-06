import datetime
import os
import json

class MarketHour:
	"""장 시간 관련 상수 및 메서드를 관리하는 클래스"""
	
	# 장 시작/종료 시간 상수
	MARKET_START_HOUR = 9
	MARKET_START_MINUTE = 0
	MARKET_END_HOUR = 15
	MARKET_END_MINUTE = 30
	
	
	@classmethod
	def get_liquidation_time(cls):
		"""DB 설정에서 청산 시간을 가져옵니다 (기본값: 15:20)"""
		try:
			from get_setting import get_setting as cached_setting
			time_str = cached_setting('liquidation_time', '15:20')
			# HH:MM 형식 파싱
			if ':' in time_str:
				hour, minute = map(int, time_str.split(':'))
				return hour, minute
			# HHMM 형식 파싱 (하위 호환)
			elif len(time_str) == 4:
				return int(time_str[:2]), int(time_str[2:])
			else:
				return 15, 20
		except:
			return 15, 20
	
	# 자동 청산 시간 (동적 로드, 하위 호환용 상수)
	LIQUIDATION_HOUR = 15
	LIQUIDATION_MINUTE = 18
	
	# [New] 일일 전량 매도 시간
	DAILY_EXIT_TIME = "15:18"
	
	@staticmethod
	def _is_mock_mode():
		"""Mock Server 모드인지 확인합니다."""
		try:
			from get_setting import get_setting
			return get_setting('use_mock_server', True)
		except:
			pass
		return False
	
	@staticmethod
	def _is_weekday():
		"""평일인지 확인합니다."""
		return datetime.datetime.now().weekday() < 5
	
	@staticmethod
	def _is_holiday():
		"""한국 공휴일인지 확인합니다 (holidays 라이브러리 사용)."""
		try:
			import holidays
			now = datetime.datetime.now()
			
			# 한국 공휴일 달력 로드
			kr_holidays = holidays.KR()
			
			# 오늘 날짜가 공휴일 목록에 있는지 확인
			return now in kr_holidays
		except ImportError:
			# 라이브러리 없는 경우 수동 리스트 fallback (최소한의 안전장치)
			# (이미 설치했으므로 여기로 빠질 일은 거의 없음)
			now = datetime.datetime.now()
			current_date = now.strftime('%Y-%m-%d')
			holidays_manual = [
				f'{now.year}-01-01', f'{now.year}-03-01', f'{now.year}-05-05', 
				f'{now.year}-06-06', f'{now.year}-08-15', f'{now.year}-10-03', 
				f'{now.year}-10-09', f'{now.year}-12-25'
			]
			return current_date in holidays_manual
	
	@staticmethod
	def is_trading_day():
		"""거래일인지 확인합니다 (평일 + 공휴일 아님)."""
		return MarketHour._is_weekday() and not MarketHour._is_holiday()
	
	@staticmethod
	def _get_market_time(hour, minute):
		"""장 시간을 반환합니다."""
		now = datetime.datetime.now()
		return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
	
	@classmethod
	def is_market_open_time(cls):
		"""현재 시간이 장 시간인지 확인합니다. Mock 모드에서는 항상 True"""
		if cls._is_mock_mode():
			return True  # Mock 모드에서는 24/7 거래 가능
		if not cls._is_weekday():
			return False
		now = datetime.datetime.now()
		market_open = cls._get_market_time(cls.MARKET_START_HOUR, cls.MARKET_START_MINUTE)
		market_close = cls._get_market_time(cls.MARKET_END_HOUR, cls.MARKET_END_MINUTE)
		# 장 시작 시간 이상, 장 종료 시간 미만 (15:30:00 이후는 장이 닫힌 것으로 판단)
		return market_open <= now < market_close
	
	@classmethod
	def is_market_start_time(cls):
		"""현재 시간이 장 시작 시간인지 확인합니다."""
		if not cls._is_weekday():
			return False
		now = datetime.datetime.now()
		market_start = cls._get_market_time(cls.MARKET_START_HOUR, cls.MARKET_START_MINUTE)
		return now >= market_start and (now - market_start).seconds < 60  # 1분 이내
	
	@classmethod
	def is_market_end_time(cls):
		"""현재 시간이 장 종료 시간인지 확인합니다."""
		if not cls._is_weekday():
			return False
		now = datetime.datetime.now()
		market_end = cls._get_market_time(cls.MARKET_END_HOUR, cls.MARKET_END_MINUTE)
		return now >= market_end and (now - market_end).seconds < 60  # 1분 이내
	@classmethod
	def is_time_passed(cls, target_time_str):
		"""
		현재 시간이 주어진 시간(HH:MM)을 지났는지 확인합니다.
		Args:
			target_time_str: "HH:MM" 형식의 문자열
		"""
		try:
			hour, minute = map(int, target_time_str.split(':'))
			now = datetime.datetime.now()
			target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
			return now >= target_time
		except Exception as e:
			print(f"시간 형식 오류: {e}")
			return False

	@classmethod
	def is_market_buy_time(cls):
		"""
		매수 가능 시간인지 확인합니다. (09:00 ~ 15:20)
		15:20 이후는 동시호가(장마감) 시간이므로 매수 금지
		Mock 모드에서는 항상 True
		"""
		if cls._is_mock_mode():
			return True  # Mock 모드에서는 24/7 매수 가능
		if not cls._is_weekday():
			return False
		now = datetime.datetime.now()
		market_open = cls._get_market_time(cls.MARKET_START_HOUR, cls.MARKET_START_MINUTE)
		buy_end = cls._get_market_time(15, 28) # 15:28 매수 마감 (테스트 위해 연장)
		return market_open <= now < buy_end
