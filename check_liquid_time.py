from database_helpers import get_setting

val = get_setting('liquidation_time')
print(f"현재 DB 설정값: liquidation_time = {val}")
