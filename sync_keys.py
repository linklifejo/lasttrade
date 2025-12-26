from database_helpers import get_setting, save_setting

# 실전 투자 Key를 가져와서 모의 투자 Key로 복사
real_key = get_setting('real_app_key', '')
real_secret = get_setting('real_app_secret', '')

if real_key and real_secret:
    print(f"실전 Key를 모의투자 Key로 복사합니다. (Key: {real_key[:5]}...)")
    save_setting('paper_app_key', real_key)
    save_setting('paper_app_secret', real_secret)
    print("복사 완료.")
else:
    print("경고: 저장된 실전 Key가 없습니다. 복사할 수 없습니다.")
