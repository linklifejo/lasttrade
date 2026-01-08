from database_helpers import save_setting
from kiwoom_adapter import reset_api

print("⚙️ 자동 시작(auto_start) 강제 활성화 중...")

# 1. 자동 시작 켜기
save_setting('auto_start', True)

# 2. Mock 모드 확실히 하기
save_setting('use_mock_server', True)
save_setting('trading_mode', 'MOCK')

print("✅ 설정 완료: auto_start=True, Mock Mode=True")
