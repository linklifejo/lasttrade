import asyncio
from kiwoom_adapter import get_api, fn_au10001
import json
import requests
import config

async def debug_outstanding():
    # 1. API 인스턴스 및 토큰 가져오기
    api = get_api()
    token = fn_au10001()
    
    print(f"--- 미체결 주문 디버그 조회 ---")
    if not token:
        print("토큰 없음")
        return

    # 직접 API 호출 시도 (RealKiwoomAPI 내부 로직 재현)
    endpoint = '/api/dostk/acnt'
    url = api.host_url + endpoint
    
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': 'N',
        'next-key': '',
        'api-id': 'ka10075',
    }
    
    if api.my_account:
        headers['cano'] = str(api.my_account)
    
    params = {
        'dmst_stex_tp': '0',        # 0: 전체
        'qry_tp': '0',              # 0: 조회구분
        'trde_tp': '0',             # 0: 전체 (필수)
        'all_stk_tp': '0',          # 0: 전체 (필수)
        'stex_tp': '0',             # 0: 전체 (필수)
        'stk_cd': ''
    }

    try:
        print(f"URL: {url}")
        print(f"Headers: {headers}")
        response = requests.post(url, headers=headers, json=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Full Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # 실제 API의 정체 확인
        raw_orders = result.get('output', [])
        if not raw_orders:
            raw_orders = result.get('ordr_list', [])
        
        print(f"Found {len(raw_orders)} raw orders.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_outstanding())
