from database_helpers import save_setting
save_setting('sell_rebuy_wait_seconds', '60')
print("Reverted sell_rebuy_wait_seconds to 60 (1 minute)")
