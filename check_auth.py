from database_helpers import get_setting
settings = [
    'real_app_key', 'real_app_secret', 
    'paper_app_key', 'paper_app_secret',
    'my_account', 'use_mock_server', 'is_paper_trading', 'trading_mode'
]
for s in settings:
    val = get_setting(s)
    if 'key' in s or 'secret' in s:
        # Mask keys
        print(f"{s}: {str(val)[:5]}... (Len: {len(str(val)) if val else 0})")
    else:
        print(f"{s}: {val}")
