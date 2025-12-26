import requests
import json
import pandas as pd
import config
from config import host_url
from login import fn_au10001 as get_token

# config.py에서 my_account가 없어도 에러나지 않게 처리
my_account = getattr(config, 'my_account', '')

# 계좌평가현황요청 (통합 데이터 반환: 종목리스트 + 계좌요약)
def get_account_data(cont_yn='N', next_key='', token=None, max_retries=2):
    """
    계좌 평가 현황 조회 (kt00004 API)
    
    Args:
        cont_yn: 연속조회 여부
        next_key: 연속조회 키
        token: 인증 토큰
        max_retries: 최대 재시도 횟수
        
    Returns:
        tuple: (종목 리스트, 계좌 요약 데이터)
    """
    # [토큰 검증]
    if not token:
        print("토큰이 None입니다. API 호출을 건너뜁니다.")
        return [], {}
    
    # 1. 요청할 API URL
    endpoint = '/api/dostk/acnt'
    url = host_url + endpoint

    # 2. header 데이터
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'kt00004',
    }
    
    if my_account:
        headers['cano'] = my_account

    # 3. 요청 데이터
    params = {
        'qry_tp': '0',
        'dmst_stex_tp': 'KRX',
    }

    all_stocks = []
    summary_data = {}
    first_call = True
    retry_count = 0
    
    while True:
        headers['cont-yn'] = cont_yn
        headers['next-key'] = next_key
        
        try:
            response = requests.post(url, headers=headers, json=params, timeout=10)
        except requests.exceptions.Timeout:
            print(f"API 요청 시간 초과 (acc_val, retry {retry_count}/{max_retries})")
            if retry_count < max_retries:
                retry_count += 1
                import time
                time.sleep(0.2)
                continue
            return [], {}
        
        try:
            response_data = response.json()
            # print(f"DEBUG: API Body: {json.dumps(response_data, ensure_ascii=False)}") 
        except requests.exceptions.JSONDecodeError:
            print("API 응답 디코딩 실패.")
            if retry_count < max_retries:
                retry_count += 1
                import time
                time.sleep(0.2)
                continue
            return [], {}

        # 첫 번째 호출의 요약 데이터 저장 (tdy_lspft_amt 등은 첫 응답에 포함)
        if first_call:
            summary_data = response_data
            first_call = False

        # stocks append
        stocks = response_data.get('stk_acnt_evlt_prst', [])
        if stocks:
            all_stocks.extend(stocks)
        
        # Check next key
        res_headers = response.headers
        cont_yn_res = res_headers.get('cont-yn', 'N')
        next_key_res = res_headers.get('next-key', '')
        
        if cont_yn_res == 'Y' and next_key_res:
             cont_yn = 'Y'
             next_key = next_key_res
             import time
             time.sleep(0.1)
        else:
             break
    
    return all_stocks, summary_data

# (구) 호환성 유지용 함수: 종목 리스트만 반환
def fn_kt00004(print_df=False, cont_yn='N', next_key='', token=None):
    raw_stocks, _ = get_account_data(cont_yn, next_key, token)
    
    if not raw_stocks:
        return []

    # [Fix] 보유수량이 0인 종목(매도 직후 잔재 등) 필터링
    stocks = []
    for s in raw_stocks:
        try:
             qty = int(s.get('rmnd_qty', '0'))
             if qty > 0:
                 stocks.append(s)
        except:
             pass

    if print_df:
        # 데이터프레임 생성 시 필요한 컬럼만 선택하되, 없는 컬럼은 제외
        available_cols = ['stk_cd', 'stk_nm', 'pl_rt', 'rmnd_qty']
        try:
            df = pd.DataFrame(stocks)
            # 존재하는 컬럼만 선택
            cols_to_use = [col for col in available_cols if col in df.columns]
            if cols_to_use:
                df = df[cols_to_use]
                pd.set_option('display.unicode.east_asian_width', True)
                print(df.to_string(index=False))
        except Exception:
            pass

    return stocks

# 보유 주식의 총 평가금액을 계산하여 반환
def get_total_eval_amt(token=None):
    try:
        stocks = fn_kt00004(token=token)
        total_eval = 0
        if not stocks:
            # print("보유 주식이 없습니다.")
            return 0
            
        for stock in stocks:
            # evlu_amt(평가금액) 필드가 있으면 사용
            if 'evlu_amt' in stock and stock['evlu_amt']:
                amt = int(stock['evlu_amt'])
                total_eval += amt
                # print(f"종목 {stock.get('stk_nm')} 평가금액: {amt}원 (API제공)")
            # 없으면 현재가 * 수량 (대략적인 계산)
            elif 'cur_prc' in stock and 'rmnd_qty' in stock:
                 price = int(stock.get('cur_prc', 0))
                 qty = int(stock.get('rmnd_qty', 0))
                 amt = price * qty
                 total_eval += amt
                 # print(f"종목 {stock.get('stk_nm')} 평가금액(계산): {amt}원 ({price}원 * {qty}주)")
            else:
                 pass
        
        # print(f"--> 총 주식 평가금액 합계: {total_eval}원")
        return total_eval
    except Exception as e:
        print(f"총 평가금액 계산 중 오류: {e}")
        return 0

# 실행 구간
if __name__ == '__main__':
    token = get_token()
    fn_kt00004(True, token=token)
    print(f"총 평가금액: {get_total_eval_amt(token)}")