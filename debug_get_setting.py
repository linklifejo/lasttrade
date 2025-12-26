from database_helpers import get_setting
import os

print(f"PID: {os.getpid()}")
use_mock = get_setting('use_mock_server', True)
is_paper = get_setting('is_paper_trading', True)
mode = get_setting('trading_mode')

print(f"use_mock_server: {use_mock} (type: {type(use_mock)})")
print(f"is_paper_trading: {is_paper} (type: {type(is_paper)})")
print(f"trading_mode: {mode} (type: {type(mode)})")
