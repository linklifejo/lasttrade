import asyncio
from kiwoom_adapter import get_api, fn_au10001
import json
import requests

async def debug_accounts():
    api = get_api()
    token = fn_au10001()
    
    print(f"--- 계좌 및 미체결 테스트 ---")
    if not token:
        print("토큰 없음")
        return

    # 1. 현재 설정된 계좌
    print(f"현재 설정된 my_account: {api.my_account}")

    # 2. 미체결 조회 (cano 없이)
    url = api.host_url + '/api/dostk/acnt'
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'api-id': 'ka10075',
    }
    
    params = {
        'dmst_stex_tp': '0',
        'qry_tp': '0',
        'trde_tp': '0',
        'all_stk_tp': '0',
        'stex_tp': '0',
        'stk_cd': ''
    }

    try:
        print("\n[Case 1] cano 없이 조회 시도...")
        res = requests.post(url, headers=headers, json=params)
        data = res.json()
        orders = data.get('output', [])
        print(f"Found {len(orders)} orders.")
        if orders:
            for o in orders:
                print(f" - 계좌: {o.get('acnt_no')}, 종목: {o.get('stk_nm')}, 미체결: {o.get('oso_qty')}")
    except Exception as e:
        print(f"Error 1: {e}")

    # 3. cano=500081996340 로 조회
    try:
        print(f"\n[Case 2] cano=500081996340 조회 시도...")
        headers['cano'] = '500081996340'
        res = requests.post(url, headers=headers, json=params)
        data = res.json()
        orders = data.get('output', [])
        print(f"Found {len(orders)} orders.")
    except Exception as e:
        print(f"Error 2: {e}")

    # 4. cano=8117045111 로 조회
    try:
        print(f"\n[Case 3] cano=8117045111 조회 시도...")
        headers['cano'] = '8117045111'
        res = requests.post(url, headers=headers, json=params)
        data = res.json()
        orders = data.get('output', [])
        print(f"Found {len(orders)} orders.")
    except Exception as e:
        print(f"Error 3: {e}")

if __name__ == "__main__":
    asyncio.run(debug_accounts())
