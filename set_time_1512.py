from database_helpers import save_setting
from market_hour import MarketHour

# 1. 청산 시간을 15:12로 설정 (내일을 위해)
save_setting('liquidation_time', '15:12')
print("✅ 청산 시간 설정 완료: 15:12 (골든타임)")

# 2. 봇이 인식하는지 테스트 출력
h, m = MarketHour.get_liquidation_time()
print(f"🤖 봇 인식 시간: {h:02d}:{m:02d}")
