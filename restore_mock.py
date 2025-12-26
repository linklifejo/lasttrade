from database_helpers import save_setting

# 설정을 'Mock Server(가상 매매)' 모드로 변경
save_setting('use_mock_server', True)
save_setting('is_paper_trading', False) # 혼동 방지를 위해 Paper는 끔

print("설정을 'Mock 모드(가상 매매)'로 변경했습니다.")
print("이제 API Key나 계좌번호와 무관하게 가상 환경에서 동작합니다.")
