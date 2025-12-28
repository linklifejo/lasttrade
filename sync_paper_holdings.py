import sys
import time
import json
import sqlite3
import requests
from kiwoom.real_api import RealKiwoomAPI
from database_helpers import get_setting

def sync_paper_holdings():
    print("🚀 [Sync] Paper Trading Holdings Synchronization Started...")
    
    # 1. DB에서 인증 정보 로드
    app_key = get_setting('paper_app_key')
    app_secret = get_setting('paper_app_secret')
    acc_no = get_setting('account_no') # 계좌번호 (공용일 수 있음)
    
    if not app_key or not app_secret:
        print("❌ Error: Paper API Key/Secret not found in DB.")
        return
        
    print(f"🔑 App Key Loaded: {app_key[:5]}***")
    
    # 2. API 인스턴스 생성 및 토큰 발급
    # is_paper=True 필수 (클래스 내부 로직에 따름, RealKiwoomAPI는 config를 보므로 여기서 주입이 어려울 수 있음)
    # 하지만 RealKiwoomAPI는 __init__에서 config를 읽음.
    # config 모듈을 직접 패치해서 모의투자로 동작하게 해야 함.
    import config
    config.app_key = app_key
    config.app_secret = app_secret
    
    # RealKiwoomAPI 인스턴스
    api = RealKiwoomAPI()
    # is_paper 플래그는 보통 URL을 결정하는데, RealKiwoomAPI는 host_url을 config에서 읽음.
    # 모의투자 URL로 교체 필요
    api.host_url = "https://openapi.koreainvestment.com:29443" # 모의투자 URL
    
    token = api.get_token()
    if not token:
        print("❌ Error: Failed to get Access Token from Paper Server.")
        print("   (Check your App Key/Secret or API Server status)")
        return
        
    print(f"✅ Token Issued: {token[:10]}...")
    
    # 3. 잔고 조회 (opw00018)
    if not acc_no:
        print("⚠️ Warning: Account No not found. Using first available account if possible.")
        # 계좌번호가 없으면 진행 불가할 수 있음
        return

    print(f"📡 Fetching holdings for Account: {acc_no}...")
    
    try:
        # opw00018: 계좌평가잔고내역요청
        # 모의투자는 실전과 동일한 TR 사용
        # 연속조회 미지원 가정 (단일 페이지)
        headers = {
            "authorization": f"Bearer {token}",
            "appKey": app_key,
            "appSecret": app_secret,
            "tr_id": "opw00018", # API 문서 참조
            "custtype": "P", # 개인
        }
        
        # 실제 REST API 호출 로직은 kiwoom_adapter.py의 get_my_stocks 참조
        # 여기서는 직접 구현하여 확실하게 가져옴
        import kiwoom_adapter
        # Adapter의 함수를 재사용하는 것이 안전함 (URL 등)
        holdings = kiwoom_adapter.get_my_stocks(token=token, is_paper=True)
        
        if holdings is None:
             print("❌ Error: Failed to fetch holdings (API Error).")
             return
             
        print(f"✅ Fetched {len(holdings)} stocks from Paper Server.")
        
        for stock in holdings:
            name = stock.get('stk_nm')
            qty = stock.get('rmnd_qty')
            pl_rt = stock.get('pl_rt')
            print(f"   - {name}: {qty}주 (수익률: {pl_rt}%)")
            
        # 4. DB/파일 저장 (봇이 인식할 수 있도록)
        # 봇은 보통 실시간으로 API를 조회하므로, 이 스크립트가 '저장'할 필요는 없지만
        # 사용자 요청("가져다 넣어라")에 따라 MOCK DB에 주입할 수도 있음.
        # 하지만 가장 좋은 건 '현재 잔고 파일'을 업데이트하는 것.
        
        # 여기서는 확인용 출력을 우선으로 함.
        # 만약 Mock 모드인 봇에게 강제로 이 정보를 주입하려면?
        # -> Mock DB init 시점에 이 정보를 로드하게 하거나, JSON 파일로 저장.
        
        with open('paper_holdings_snapshot.json', 'w', encoding='utf-8') as f:
            json.dump(holdings, f, ensure_ascii=False, indent=4)
        print("💾 Saved snapshot to 'paper_holdings_snapshot.json'")

    except Exception as e:
        print(f"❌ Error during sync: {e}")

if __name__ == "__main__":
    sync_paper_holdings()
