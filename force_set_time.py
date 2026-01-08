from database_helpers import save_setting, get_setting

# 1. DB에 강제로 15:12 저장
save_setting('liquidation_time', '15:12')

# 2. 확인
val = get_setting('liquidation_time')
print(f"DB 저장 결과: liquidation_time = {val}")

if str(val) == '15:12':
    print("✅ 성공적으로 저장되었습니다.")
else:
    print("❌ 저장 실패 (다른 로직이 덮어씀)")
