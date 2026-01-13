from kiwoom_adapter import fn_kt10001, get_token, get_api
import asyncio

async def check_ohlc(code):
    api = get_api()
    token = get_token()
    # fn_kt10001 might not be the right one for quote, let's use a generic method if available
    # Actually KIS API has a quote endpoint. In our adapter it might be different.
    # Let's just check the last recorded price in our DB or something?
    # Or use the adapter's existing functionality.
    pass

if __name__ == "__main__":
    # Just check the logs for 013720 specifically.
    pass
