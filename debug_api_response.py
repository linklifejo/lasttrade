from kiwoom.real_api import RealKiwoomAPI
import asyncio
import json

async def test_balance():
    api = RealKiwoomAPI()
    
    print("--- API Token Issuance ---")
    token = api.get_token() # get_token() 메서드 사용
    if not token:
        print("Token failed")
        return
    
    print(f"Token (First 10 char): {token[:10]}...")
    print(f"Current Account: {api.my_account}")
    
    print("\n--- Getting Balance ---")
    # 계좌 정보를 요청
    res = api.get_balance(token=token)
    print(f"Final Result: {res}")

if __name__ == "__main__":
    asyncio.run(test_balance())
