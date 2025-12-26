from database_helpers import save_setting

# 설정을 '키움 모의투자(Paper Trading API)' 모드로 변경
save_setting('use_mock_server', False)  # API 사용
save_setting('is_paper_trading', True)  # Paper 모드

print("설정을 '키움 모의투자(API)' 모드로 변경했습니다.")
print("주의: 모의투자 전용 App Key가 설정되어 있지 않으면 403 에러가 발생할 수 있습니다.")
