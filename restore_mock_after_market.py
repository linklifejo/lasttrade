from database_helpers import save_setting
from kiwoom_adapter import reset_api
import time

print("💤 장 마감 후 MOCK 모드(휴식)로 복귀 설정 중...")

# 장 마감 후엔 Mock 모드로 대기하는 것이 안전함
save_setting('trading_mode', 'MOCK')
save_setting('use_mock_server', True)

# API 인스턴스 초기화 (다음 호출 시 Mock으로 생성됨)
reset_api()

print("✅ 설정 복구 완료. 내일 아침 09:00에 자동으로 REAL로 전환될 것입니다.")
