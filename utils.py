"""
유틸리티 함수 모음
"""
import os
import json
import datetime
from logger import logger

def log_trading_event(type, code, name, qty, price, profit_rate=0, reason=""):
    """
    통합 매매 일지 저장 (DB 방식으로 변경)
    - JSON 파일 손상 문제 해결
    - 대시보드 '매매보고서' 탭에서 사용하는 데이터 소스
    """
    try:
        from database_trading_log import log_buy_to_db, log_sell_to_db
        
        # [Mode Check] 3단 분리 (MOCK / PAPER / REAL)
        mode_str = "REAL"  # Default
        try:
            from database_helpers import get_setting
            use_mock = get_setting('use_mock_server', False)
            if use_mock:
                mode_str = "MOCK"
            else:
                is_paper = get_setting('is_paper_trading', True)
                if is_paper:
                    mode_str = "PAPER"
                else:
                    mode_str = "REAL"
        except: 
            pass
        
        # DB에 저장
        if type.lower() == 'buy':
            log_buy_to_db(code, name, qty, price, mode_str)
        else:
            log_sell_to_db(code, name, qty, price, profit_rate, reason, mode_str)
            
        logger.info(f"📝 매매일지 DB 기록 완료: {type} {name} ({code}) [{mode_str}]")
        
    except Exception as e:
        logger.error(f"매매일지 DB 기록 실패: {e}")

def normalize_stock_code(code):
    """
    종목 코드를 정규화합니다.
    키움 API에서 'A'로 시작하는 종목 코드를 순수 숫자 코드로 변환합니다.
    
    Args:
        code (str): 종목 코드 (예: 'A005930' 또는 '005930')
        
    Returns:
        str: 정규화된 종목 코드 (예: '005930')
        
    Examples:
        >>> normalize_stock_code('A005930')
        '005930'
        >>> normalize_stock_code('005930')
        '005930'
        >>> normalize_stock_code('0A5930')  # 잘못된 경우도 안전하게 처리
        '0A5930'
    """
    if not code:
        return code
    
    # 'A'로 시작하는 경우에만 제거
    if isinstance(code, str) and code.startswith('A'):
        return code[1:]
    
    return code


def validate_api_response(data, required_fields=None, allow_zero=False):
    """
    API 응답 데이터를 검증합니다.
    
    Args:
        data (dict): API 응답 데이터
        required_fields (list): 필수 필드 목록
        allow_zero (bool): 0 값을 허용할지 여부
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not data:
        return False, "Empty response data"
    
    if required_fields:
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return False, f"Missing required fields: {missing_fields}"
    
    # 모든 필드가 0인지 확인 (API 타임아웃/오류 감지)
    if not allow_zero and isinstance(data, dict):
        numeric_fields = []
        for key, value in data.items():
            try:
                # 문자열을 정수로 변환 시도
                num_val = int(str(value).replace(',', ''))
                numeric_fields.append(num_val)
            except (ValueError, AttributeError):
                continue
        
        # 숫자 필드가 있고 모두 0이면 의심스러운 응답
        if numeric_fields and all(v == 0 for v in numeric_fields):
            return False, "All numeric fields are zero (possible API error)"
    
    return True, None
