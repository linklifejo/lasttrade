from database_helpers import get_setting
print(f"use_mock_server: {get_setting('use_mock_server')}")
print(f"is_paper_trading: {get_setting('is_paper_trading')}")
