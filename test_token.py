from kiwoom_adapter import get_token, get_api, get_current_api_mode
from logger import logger
import traceback

def test_token():
    print(f"Current API Mode: {get_current_api_mode()}")
    try:
        # fn_au10001은 인자를 받지 않음. 내부에서 실시간으로 획득 시도함.
        from kiwoom_adapter import fn_au10001
        token = fn_au10001()
        if token:
            print(f"✅ Token acquisition success: {token[:10]}...")
        else:
            print("❌ Token acquisition failed (None)")
            # 왜 실패했는지 real_api.py의 로그를 확인해야 함
    except Exception as e:
        print(f"💥 Error during token acquisition: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_token()
