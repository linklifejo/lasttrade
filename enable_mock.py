from database_helpers import save_setting
# Mock Server 강제 활성화 (24시간 테스트를 위해)
save_setting('use_mock_server', '1')
print("Enabled Mock Server Mode (24/7 Trading)")
