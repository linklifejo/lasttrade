
from database_trading_log import log_sell_to_db, get_trading_logs_from_db
import datetime

print("Testing DB Insert...")
try:
    # 가짜 매도 기록 생성
    log_sell_to_db("000000", "TEST_STOCK", 10, 10000, 5.0, "Test Sell", "MOCK")
    print("Insert function called.")
except Exception as e:
    print(f"Insert failed: {e}")

print("\nVerifying DB...")
today = datetime.datetime.now().strftime('%Y-%m-%d')
logs = get_trading_logs_from_db(mode='MOCK', limit=10, date=today)
found = False
for sell in logs['sells']:
    print(sell)
    if sell['stk_cd'] == "000000" and sell['stk_nm'] == "TEST_STOCK":
        found = True

if found:
    print("\n✅ SUCCESS: Test sell record found in DB.")
else:
    print("\n❌ FAILED: Test sell record NOT found in DB.")
