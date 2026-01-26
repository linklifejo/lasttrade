"""
키움 API Factory

설정에 따라 실제 API 또는 Mock API를 생성합니다.
"""

from .base_api import KiwoomAPI
from .real_api import RealKiwoomAPI
from .mock_api import MockKiwoomAPI
from logger import logger
import json
import os


def create_kiwoom_api(use_mock: bool = None) -> KiwoomAPI:
    """
    키움 API 인스턴스 생성
    
    Args:
        use_mock: True면 Mock API, False면 Real API, None이면 DB에서 읽음
        
    Returns:
        KiwoomAPI: 키움 API 인스턴스
    """
    if use_mock is None:
        try:
            from get_setting import get_setting
            use_mock = get_setting('use_mock_server', False)
        except Exception as e:
            logger.warning(f"설정 조회 실패, 기본값(Mock API) 사용: {e}")
            use_mock = True
    
    if use_mock:
        logger.info("🎮 내부 Mock 시뮬레이터 사용 (Internal Simulation Mode)")
        return MockKiwoomAPI()
    else:
        logger.info("📡 키움 서버 접속 모드 (Real/Paper Trading Mode)")
        return RealKiwoomAPI()


def get_api_status() -> dict:
    """
    현재 API 상태 조회
    
    Returns:
        dict: API 모드 및 상태 정보
    """
    try:
        from get_setting import get_setting
        use_mock = get_setting('use_mock_server', False)
            
        return {
            "mode": "MOCK" if use_mock else "REAL",
            "description": "가상 서버" if use_mock else "실제 서버",
            "is_mock": use_mock
        }
    except Exception as e:
        return {
            "mode": "UNKNOWN",
            "description": f"상태 조회 실패: {e}",
            "is_mock": True
        }
