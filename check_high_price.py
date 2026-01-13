from kiwoom_adapter import get_active_api, get_token
import asyncio

async def check_ohlc():
    api = get_active_api()
    token = get_token()
    # KIS API: Get Quote
    # Need to check the adapter for available methods
    pass

if __name__ == "__main__":
    # check_current_pl.py showed 9.40% at 09:10.
    pass
