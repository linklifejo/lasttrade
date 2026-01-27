import json
import os
from datetime import datetime

# [Dynamic Config] Smart Mode Switching
# 기본적으로 settings.json을 따르되, "평일 장 운영 시간(08:00~16:00)"에는 
# 설령 Mock 설정이 켜져 있더라도 강제로 [실전(Real)] 모드로 진입합니다.

try:
    from database_helpers import get_setting
except Exception as e:
    try:
        from get_setting import get_setting
    except:
        def get_setting(key, default): return default

def log_config():
    try:
        print(f"[Config] 📡 현재 환경: {_cfg.env_desc}")
    except: pass
# [Dynamic Config Class] DB에서 실시간으로 값을 가져오기 위한 클래스
class BotConfig:
    @property
    def is_paper_trading(self):
        return get_setting('is_paper_trading', False)

    @property
    def user_mock_setting(self):
        return get_setting('use_mock_server', False)

    @property
    def real_app_key(self):
        val = get_setting('real_app_key', "ueEZm8xQX19MdIZDgr764cmS1ve5jogRVb9LpYVE-Rk")
        ret = val.strip() if val else val
        # logger.info(f"Config - real_app_key retrieved: {ret[:5]}...")
        return ret

    @property
    def real_app_secret(self):
        val = get_setting('real_app_secret', "OHpBObbQNxebGpC7GKU5faXstXPzhdNestWebFMhb6A")
        return val.strip() if val else val

    @property
    def paper_app_key(self):
        val = get_setting('paper_app_key', "I8zHt-F_c9LPHCab9S0IsaPAxW_2N4Wx0AXUKZ9fX0I")
        return val.strip() if val else val

    @property
    def paper_app_secret(self):
        val = get_setting('paper_app_secret', "lQcU0XYj0SzVxAf8P-f5Uv4wxxywGZbPZq-LMrt2_MQ")
        return val.strip() if val else val

    @property
    def telegram_chat_id(self):
        return get_setting('telegram_chat_id', "8586247146")

    @property
    def telegram_token(self):
        return get_setting('telegram_token', "8597712986:AAEiRPcWHsVPkVNS3mp7CHDAahgpXAQm7rs")

    @property
    def my_account(self):
        return get_setting('my_account', "500081996340")

    @property
    def app_key(self):
        return self.paper_app_key if self.is_paper_trading else self.real_app_key

    @property
    def app_secret(self):
        return self.paper_app_secret if self.is_paper_trading else self.real_app_secret

    @property
    def host_url(self):
        return "https://mockapi.kiwoom.com" if self.is_paper_trading else "https://api.kiwoom.com"

    @property
    def socket_url(self):
        return "wss://mockapi.kiwoom.com:10000" if self.is_paper_trading else "wss://api.kiwoom.com:10000"

    @property
    def liquidation_time(self):
        return get_setting('liquidation_time', '15:20')

    @property
    def market_code(self):
        return get_setting('market_code', 'KRX')

    @property
    def env_desc(self):
        mode = "모의투자(Paper)" if self.is_paper_trading else "실전투자(Real)"
        backend = " + 내부Mock" if self.user_mock_setting else " + 키움API"
        return f"{mode}{backend}"

# 인스턴스 생성
_cfg = BotConfig()

# 기존 코드와의 호환성을 위한 래퍼 변수들 (매번 get_setting 호출)
class DynamicProxy:
    def __init__(self, key):
        self.key = key
    def __str__(self):
        return str(getattr(_cfg, self.key))
    def __repr__(self):
        return str(getattr(_cfg, self.key))
    def __eq__(self, other):
        return getattr(_cfg, self.key) == other

# 실제 변수 접근 시 실시간으로 가져오도록 함
def __getattr__(name):
    if hasattr(_cfg, name):
        return getattr(_cfg, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# 초기 로깅을 위한 일시적 변수 (필요한 경우)
is_paper_trading = _cfg.is_paper_trading
user_mock_setting = _cfg.user_mock_setting
market_code = "KRX"

class MarketHour:
    """장 운영 시간 및 자동 청산 시간 관리 (DB 연동)"""
    
    @staticmethod
    def get_liquidation_time():
        """DB에서 최신 청산 시간을 가져와 시, 분 반환"""
        try:
            time_str = _cfg.liquidation_time
            h, m = map(int, time_str.split(':'))
            return h, m
        except:
            return 15, 20

    @staticmethod
    def is_market_open_time():
        """현재 시간이 장 운영 시간(09:00 ~ 15:30)인지 확인"""
        now = datetime.now()
        current_time = now.hour * 100 + now.minute
        return 900 <= current_time <= 1530

    @staticmethod
    def is_time_passed(target_time_str=None):
        """특정 시간(기본값: DB의 청산시간)이 지났는지 확인"""
        try:
            if target_time_str is None:
                target_hour, target_minute = MarketHour.get_liquidation_time()
            else:
                target_hour, target_minute = map(int, target_time_str.split(':'))
                
            now = datetime.now()
            if now.hour > target_hour:
                return True
            if now.hour == target_hour and now.minute >= target_minute:
                return True
            return False
        except:
            return False

# [Global] 실시간 상태 추적
outstanding_orders = {}
stocks_being_sold = set() # 현재 매도 프로세스가 진행 중인 종목들
ai_recommendation_queue = [] # [AI] 추천 대기열 (스레드에서 넣고 봇이 처리)


# [API Helper] 현재 설정에 맞는 API 객체 반환
def get_api():
    """현재 설정(Mock/Real/Paper)에 따라 적절한 API 객체를 반환합니다."""
    try:
        # user_mock_setting 변수가 정의되어 있는지 확인
        # use_mock = globals().get('user_mock_setting', True)
        use_mock = _cfg.user_mock_setting # DB에서 실시간 값 조회
        
        if use_mock:
            # Mock API 사용
            from mock_api import MockAPI
            return MockAPI()
        else:
            # Real/Paper Kiwoom API 사용
            from kiwoom.real_api import RealKiwoomAPI
            return RealKiwoomAPI()
    except Exception as e:
        # 오류 발생 시 기본값으로 Mock API 반환
        print(f"[get_api] API 객체 생성 실패, Mock API 반환: {e}")
        from mock_api import MockAPI
        return MockAPI()
