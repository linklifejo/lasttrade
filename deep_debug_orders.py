import asyncio
from kiwoom_adapter import get_api, fn_au10001
import requests
import json

async def deep_debug():
    api = get_api()
    token = fn_au10001()
    
    if not token:
        print("토큰 실패")
        return

    # 1. 사용 가능한 모든 계좌 목록 조회 (계좌 정보 API가 있다면)
    # REST API에는 계좌 목록 조회 API가 따로 없는 경우가 많음. 
    # 하지만 통상적으로 첫 번째 계좌를 사용함.
    
    # 2. 미체결 주문 조회 (ka10075) - 가능한 모든 필드 조합 테스트
    url = api.host_url + '/api/dostk/acnt'
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'api-id': 'ka10075',
    }
    
    # 계수(cano) 없이 조회
    params = {
        'dmst_stex_tp': '0',
        'qry_tp': '0',
        'trde_tp': '0',
        'all_stk_tp': '0',
        'stex_tp': '0',
        'stk_cd': ''
    }

    test_accounts = [None, '500081996340', '8117045111']
    
    for acnt in test_accounts:
        print(f"\n--- Testing Account: {acnt} ---")
        if acnt:
            headers['cano'] = acnt
        else:
            if 'cano' in headers: del headers['cano']
            
        try:
            res = requests.post(url, headers=headers, json=params, timeout=10)
            print(f"Status: {res.status_code}")
            data = res.json()
            
            # 모든 상위 키 출력
            print(f"Keys in Response: {list(data.keys())}")
            
            # 'output' 혹은 다른 리스트 형태의 데이터 탐색
            for key, val in data.items():
                if isinstance(val, list) and len(val) > 0:
                    print(f"Found list in key '{key}' with {len(val)} items.")
                    for item in val[:3]:
                        print(f" - {item.get('stk_nm', 'NoName')}({item.get('stk_cd', 'NoCode')}): {item.get('oso_qty', 'NoQty')}")
        except Exception as e:
            print(f"Error testing {acnt}: {e}")
        
        await asyncio.sleep(1.0) # Rate limit 방어

if __name__ == "__main__":
    asyncio.run(deep_debug())
