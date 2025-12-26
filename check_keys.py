from database_helpers import get_setting
print(f"REAL_KEY: {get_setting('real_app_key')}")
print(f"PAPER_KEY: {get_setting('paper_app_key')}")
