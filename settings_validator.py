from typing import Any, Dict

class SettingsValidator:
	"""설정 값 검증 클래스 (DB 기반)"""
	
	# 설정 값의 허용 범위 및 타입
	VALIDATION_RULES = {
		'auto_start': {
			'type': bool,
			'description': '자동 시작 여부'
		},
		'use_mock_server': {
			'type': bool,
			'description': 'Mock 서버 사용 여부'
		},
		'is_paper_trading': {
			'type': bool,
			'description': '모의투자 모드 여부'
		},
		'target_stock_count': {
			'type': (int, float),
			'min': 1,
			'max': 100,
			'description': '목표 보유 종목 수'
		},
		'target_profit_amt': {
			'type': int,
			'min': 1000,
			'description': '일일 목표 수익금 (원)'
		},
		'global_loss_rate': {
			'type': (int, float),
			'min': -100.0,
			'max': -0.1,
			'description': '일일 전체 손실 제한 (%)'
		},
		'trading_capital_ratio': {
			'type': (int, float),
			'min': 1,
			'max': 100,
			'description': '투자 비중 (순자산 대비 %)'
		},
		'split_buy_cnt': {
			'type': int,
			'min': 1,
			'max': 10,
			'description': '분할 매수 횟수 (1~10)'
		},
		'use_rsi_filter': {
			'type': bool,
			'description': 'RSI 필터 사용 여부'
		},
		'rsi_limit': {
			'type': (int, float),
			'min': 1,
			'max': 100,
			'description': 'RSI 매수 제한 상한값'
		},
		'math_min_win_rate': {
			'type': (int, float),
			'min': 0,
			'max': 1.0,
			'description': '수학 엔진 최소 승률 (0.0~1.0)'
		},
		'math_min_sample_count': {
			'type': int,
			'min': 0,
			'max': 1000,
			'description': '수학 엔진 최소 표본 수'
		},
		'single_stock_strategy': {
			'type': str,
			'description': '매매 전략 (FIRE/WATER)'
		},
		'single_stock_rate': {
			'type': (int, float),
			'min': 0.1,
			'max': 20.0,
			'description': '추가 매수 간격 (%)'
		},
		'take_profit_rate': {
			'type': (int, float),
			'min': 0.1,
			'max': 100.0,
			'description': '익절 기준 (0.1% ~ 100%)'
		},
		'stop_loss_rate': {
			'type': (int, float),
			'min': -100.0,
			'max': -0.1,
			'description': '손절 기준 (-100% ~ -0.1%)'
		},
		'time_cut_minutes': {
			'type': (int, float),
			'min': 0,
			'max': 1440,
			'description': '타임컷 대기 시간 (분)'
		},
		'time_cut_profit': {
			'type': (int, float),
			'min': -100.0,
			'max': 100.0,
			'description': '타임컷 기준 수익률 (%)'
		}
	}
	
	@classmethod
	def validate_setting(cls, key: str, value: Any) -> tuple[bool, str]:
		"""설정 값을 검증합니다."""
		if key not in cls.VALIDATION_RULES:
			return True, ""
		
		rule = cls.VALIDATION_RULES[key]
		
		# 타입 검증
		expected_type = rule['type']
		if not isinstance(value, expected_type):
			# 자동 형변환 시도 (문자열 -> 숫자/불린)
			try:
				if expected_type == bool:
					if str(value).lower() in ('true', '1', 'yes'): value = True
					elif str(value).lower() in ('false', '0', 'no'): value = False
				elif expected_type in (int, float, (int, float)):
					value = float(value) if expected_type == float or isinstance(expected_type, tuple) else int(value)
			except:
				type_name = str(expected_type)
				return False, f"{key}는 {type_name} 타입이어야 합니다. (현재: {type(value).__name__})"
		
		# 범위 검증
		if isinstance(value, (int, float)):
			if 'min' in rule and value < rule['min']:
				return False, f"{key}는 {rule['min']} 이상이어야 합니다. (현재: {value})"
			if 'max' in rule and value > rule['max']:
				return False, f"{key}는 {rule['max']} 이하여야 합니다. (현재: {value})"
		
		return True, ""
	
	@classmethod
	def validate_all_settings(cls, settings: Dict[str, Any]) -> tuple[bool, list[str]]:
		"""모든 설정 값을 검증합니다."""
		errors = []
		for key, value in settings.items():
			is_valid, error_msg = cls.validate_setting(key, value)
			if not is_valid:
				errors.append(error_msg)
		return len(errors) == 0, errors
