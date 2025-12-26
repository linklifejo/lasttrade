from database_helpers import save_setting

# 사용자 요청 계좌번호 저장 및 모의투자 모드 활성화
save_setting('my_account', '81170451')
save_setting('use_mock_server', False)  # Mock Server(가상) 끄기 -> API 사용
save_setting('is_paper_trading', True)  # Paper Trading(모의투자) 켜기

print("설정 업데이트 완료: 계좌번호 81170451, API 사용, 모의투자 모드")
