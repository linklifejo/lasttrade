"""
실제 키움 API 구현체

기존 키움 REST API를 사용하는 실제 구현입니다.
"""

import requests
import json
import time
import pandas as pd
from typing import List, Dict, Tuple, Optional
from .base_api import KiwoomAPI
from logger import logger
import config


class RealKiwoomAPI(KiwoomAPI):
    """실제 키움 REST API 구현"""
    
    def __init__(self):
        self.app_key = config.app_key
        self.app_secret = config.app_secret
        self.host_url = config.host_url
        self.my_account = getattr(config, 'my_account', '')
    
    def get_token(self) -> Optional[str]:
        """접근토큰 발급"""
        endpoint = '/oauth2/token'
        url = self.host_url + endpoint
        
        # JSON 형식 사용 (가마우지/chapter_4 성공 방식)
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
        }
        
        # 요청 데이터
        data = {
            'grant_type': 'client_credentials',
            'appkey': self.app_key,
            'secretkey': self.app_secret,
        }
        
        try:
            # Debug: API 키 정보 로깅 (보안을 위해 일부만 표시)
            logger.info(f'Token request - URL: {url}')
            
            # json=data 파라미터로 전송
            response = requests.post(url, headers=headers, json=data, timeout=10)
            logger.info(f'Token request - Code: {response.status_code}')
            
            if response.status_code != 200:
                logger.warning(f'Token request failed - Response: {response.text[:200]}')
                # Mock 모드가 아닐 때만 경고
                from database_helpers import get_setting
                use_mock = get_setting('use_mock_server', True)
                if not use_mock:
                    logger.warning(f"⚠️ 토큰 발급 실패 (HTTP {response.status_code}) - API 키/Secret 또는 네트워크를 확인하세요")
                return None
            
            result = response.json()
            # 'token' 또는 'access_token' 둘 다 호환되도록 처리
            token = result.get('token') or result.get('access_token')
            if token:
                logger.info(f'✅ Token received: {token[:20]}...')
            return token
        except Exception as e:
            # Mock 모드에서는 토큰 오류 표시 안 함
            from database_helpers import get_setting
            use_mock = get_setting('use_mock_server', True)
            if not use_mock:
                logger.warning(f"⚠️ 토큰 발급 중 오류: {e}")
            return None
    
    def get_balance(self, token: str) -> Tuple[int, int, int]:
        """예수금 상세 현황 조회"""
        if not token:
            logger.error("토큰이 None입니다. API 호출을 건너뜁니다.")
            return 0, 0, 0
        
        endpoint = '/api/dostk/acnt'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'kt00001',
        }
        
        if self.my_account:
            headers['cano'] = str(self.my_account)
        
        params = {
            'qry_tp': '3',  # 조회구분 3:추정조회
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=params, timeout=10)
                data = response.json()
                
                # [Fix] 호출 제한(Error 1700) 감지 및 대응
                ret_msg = str(data.get('return_msg', ''))
                ret_code = str(data.get('return_code', ''))
                
                if '1700' in ret_msg or '허용된 요청 개수를 초과' in ret_msg or ret_code == '5':
                    logger.warning(f"[API 호출 제한] {ret_msg} (시도 {attempt + 1}/{max_retries}). 2초 대기 후 재시도...")
                    if attempt < max_retries - 1:
                        time.sleep(2.0)
                        continue
                    else:
                        logger.error("❌ 호출 제한으로 인해 잔고 조회에 최종 실패했습니다.")
                        return 0, 0, 0

                # [DEBUG] 잔고 데이터 전체 로깅 (HTS 불일치 원인 파악용)
                # logger.info(f"[Balance Debug] Account: {self.my_account}, Data Key-Values: {list(data.keys())}")
                # logger.info(f"[Balance Debug] Full Data: {data}")
                
                # [Fix] 절대값(abs) 적용: 모의투자 등에서 음수로 반환되는 경우 대응
                cutoff_amt = abs(int(str(data.get('ord_alow_amt', '0')).replace(',', '')))
                deposit_amt = abs(int(str(data.get('dnca_tot_amt', '0')).replace(',', '')))
                total_amt = abs(int(str(data.get('tot_evlu_amt', '0')).replace(',', '')))
                
                # [Fix] 만약 여전히 0이라면 다른 필드(d2_entra, entr 등) 시도
                if deposit_amt == 0:
                    deposit_amt = abs(int(str(data.get('d2_entra', '0')).replace(',', '')))
                if total_amt == 0:
                    total_amt = abs(int(str(data.get('entr', '0')).replace(',', '')))
                
                # [Fix] API 버그 대응: ord_alow_amt가 비정상적으로 작을 경우 출금가능금액(pymn_alow_amt) 사용
                if cutoff_amt < 1000000:
                    alt_amt = int(str(data.get('pymn_alow_amt', '0')).replace(',', ''))
                    if alt_amt > cutoff_amt:
                        logger.warning(f"[API 보정] 주문가능금액({cutoff_amt})이 너무 작아 출금가능금액({alt_amt})으로 대체합니다.")
                        cutoff_amt = alt_amt

                # deposit_amt = int(str(data.get('dnca_tot_amt', '0')).replace(',', ''))
                # total_amt = int(str(data.get('tot_evlu_amt', '0')).replace(',', ''))
                
                if deposit_amt == 0:
                    deposit_amt = cutoff_amt
                if total_amt == 0:
                    total_amt = deposit_amt
                
                if cutoff_amt == 0 and deposit_amt == 0 and total_amt == 0:
                    logger.warning(f"[API 검증 실패] 모든 잔고 값이 0으로 조회됨")
                    logger.info(f"[Debug Data] {data}") # JSON 구조 확인을 위해 전체 출력
                    if attempt < max_retries - 1:
                        time.sleep(1.0) # 지연 시간 증가
                        continue
                    else:
                        # [Final Fallback] 만약 모든 값이 0이면, 다른 필드라도 있는지 확인
                        # 일부 계좌에서는 'n_cash_amt' 등을 사용할 수 있음
                        fallback_amt = int(str(data.get('n_cash_amt', '0')).replace(',', ''))
                        if fallback_amt > 0:
                            logger.info(f"[Fallback 적용] n_cash_amt({fallback_amt})를 예수금으로 사용")
                            return fallback_amt, fallback_amt, fallback_amt
                        return 0, 0, 0
                
                # logger.info(f"계좌 잔고 - 주문가능: {cutoff_amt:,}, 예수금: {deposit_amt:,}, API총평가: {total_amt:,}")
                return cutoff_amt, total_amt, deposit_amt
                
            except requests.exceptions.Timeout:
                logger.error(f"API 요청 시간 초과 (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(1.0)
                    continue
            except Exception as e:
                logger.error(f"잔고 데이터 파싱 오류: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.2)
                    continue
        
        return 0, 0, 0
    
    def get_account_data(self, token: str) -> Tuple[List[Dict], Dict]:
        """계좌 평가 현황 조회"""
        if not token:
            logger.error("토큰이 None입니다. API 호출을 건너뜁니다.")
            return [], {}
        
        endpoint = '/api/dostk/acnt'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'kt00004',
        }
        
        if self.my_account:
            headers['cano'] = str(self.my_account)
        
        params = {
            'qry_tp': '0',
            'dmst_stex_tp': 'KRX',
        }
        
        all_stocks = []
        summary_data = {}
        first_call = True
        max_retries = 2
        retry_count = 0
        cont_yn = 'N'
        next_key = ''
        
        while True:
            headers['cont-yn'] = cont_yn
            headers['next-key'] = next_key
            
            try:
                response = requests.post(url, headers=headers, json=params, timeout=10)
                response_data = response.json()
                
                if first_call:
                    summary_data = response_data
                    first_call = False
                
                stocks = response_data.get('stk_acnt_evlt_prst', [])
                if stocks:
                    all_stocks.extend(stocks)
                
                res_headers = response.headers
                cont_yn_res = res_headers.get('cont-yn', 'N')
                next_key_res = res_headers.get('next-key', '')
                
                if cont_yn_res == 'Y' and next_key_res:
                    cont_yn = 'Y'
                    next_key = next_key_res
                    time.sleep(0.1)
                else:
                    break
                    
            except requests.exceptions.Timeout:
                logger.error(f"API 요청 시간 초과 (retry {retry_count}/{max_retries})")
                if retry_count < max_retries:
                    retry_count += 1
                    time.sleep(0.2)
                    continue
                return [], {}
            except Exception as e:
                logger.error(f"계좌 데이터 조회 오류: {e}")
                if retry_count < max_retries:
                    retry_count += 1
                    time.sleep(0.2)
                    continue
                return [], {}
        
        return all_stocks, summary_data
    
    def get_my_stocks(self, token: str, print_df: bool = False) -> List[Dict]:
        """보유 종목 조회"""
        raw_stocks, _ = self.get_account_data(token)
        
        if not raw_stocks:
            return []
        
        stocks = []
        for s in raw_stocks:
            try:
                qty = int(s.get('rmnd_qty', '0'))
                if qty > 0:
                    stocks.append(s)
            except:
                pass
        
        if print_df and stocks:
            try:
                df = pd.DataFrame(stocks)
                available_cols = ['stk_cd', 'stk_nm', 'pl_rt', 'rmnd_qty']
                cols_to_use = [col for col in available_cols if col in df.columns]
                if cols_to_use:
                    df = df[cols_to_use]
                    pd.set_option('display.unicode.east_asian_width', True)
                    print(df.to_string(index=False))
            except Exception:
                pass
        
        return stocks
    
    def get_total_eval_amt(self, token: str) -> int:
        """보유 주식의 총 평가금액 계산"""
        try:
            stocks = self.get_my_stocks(token)
            total_eval = 0
            
            if not stocks:
                return 0
            
            for stock in stocks:
                if 'evlu_amt' in stock and stock['evlu_amt']:
                    amt = int(stock['evlu_amt'])
                    total_eval += amt
                elif 'cur_prc' in stock and 'rmnd_qty' in stock:
                    price = int(stock.get('cur_prc', 0))
                    qty = int(stock.get('rmnd_qty', 0))
                    amt = price * qty
                    total_eval += amt
            
            return total_eval
        except Exception as e:
            logger.error(f"총 평가금액 계산 중 오류: {e}")
            return 0
    
    def buy_stock(self, stk_cd: str, ord_qty: str, ord_uv: str, token: str) -> Tuple[str, str]:
        """주식 매수 주문"""
        endpoint = '/api/dostk/ordr'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'kt10000',
        }
        
        params = {
            'dmst_stex_tp': getattr(config, 'market_code', 'KRX'),
            'stk_cd': stk_cd,
            'ord_qty': f'{ord_qty}',
            'ord_uv': f'{ord_uv}',
            'trde_tp': '0',  # 보통 주문
            'cond_uv': '',
        }
        
        try:
            response = requests.post(url, headers=headers, json=params)
            result = response.json()
            logger.info(f"매수 주문 결과(주문번호 등): {result}")
            # [AutoCancel] 주문 추적 등록
            try:
                config.outstanding_orders[time.time()] = {'type': 'buy', 'code': stk_cd, 'qty': ord_qty, 'result': result}
            except: pass
            return result.get('return_code', ''), result.get('return_msg', '')
        except Exception as e:
            logger.error(f"매수 주문 오류: {e}")
            return 'ERROR', str(e)
    
    def sell_stock(self, stk_cd: str, ord_qty: str, token: str) -> Tuple[str, str]:
        """주식 매도 주문 (시장가)"""
        endpoint = '/api/dostk/ordr'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'kt10001',
        }
        
        params = {
            'dmst_stex_tp': getattr(config, 'market_code', 'KRX'),
            'stk_cd': stk_cd,
            'ord_qty': ord_qty,
            'ord_uv': '',
            'trde_tp': '3',  # 시장가
            'cond_uv': '',
        }
        
        try:
            response = requests.post(url, headers=headers, json=params)
            result = response.json()
            logger.info(f"매도 주문 결과(주문번호 등): {result}")
            try:
                config.outstanding_orders[time.time()] = {'type': 'sell', 'code': stk_cd, 'qty': ord_qty, 'result': result}
            except: pass
            return result.get('return_code', ''), result.get('return_msg', '')
        except Exception as e:
            logger.error(f"매도 주문 오류: {e}")
            return 'ERROR', str(e)
    
    
    def get_outstanding_orders(self, token: str) -> List[Dict]:
        """미체결 주문 조회 (ka10075)"""
        endpoint = '/api/dostk/acnt'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'ka10075',
        }
        
        if self.my_account:
            headers['cano'] = str(self.my_account)
        
        params = {
            'dmst_stex_tp': '0',        # 0: 전체
            'qry_tp': '0',              # 0: 조회구분
            'trde_tp': '0',             # 0: 전체 (필수)
            'all_stk_tp': '0',          # 0: 전체 (필수)
            'stex_tp': '0',             # 0: 전체 (필수)
            'stk_cd': ''
        }


        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=params, timeout=10)
                result = response.json()
                
                # [Fix] 호출 제한(Error 1700) 감지 및 대응 (Retry logic)
                ret_code = result.get('return_code')
                ret_msg = str(result.get('return_msg', ''))
                
                if ret_code is not None and str(ret_code) == '5' or '1700' in ret_msg:
                    logger.warning(f"[미체결 호출 제한] {ret_msg} (시도 {attempt + 1}/{max_retries}). 1초 대기 후 재시도...")
                    if attempt < max_retries - 1:
                        time.sleep(1.0)
                        continue
                    else:
                        logger.error("❌ 호출 제한으로 인해 미체결 조회에 최종 실패했습니다.")
                        return None

                if str(ret_code) != '0':
                    msg = result.get('return_msg', '알 수 없는 에러')
                    logger.error(f"[미체결 조회 실패] 에러코드 {ret_code}: {msg}")
                    return None
                
                # 미체결 주문 목록 추출 및 데이터 정규화 (ka10075 전용)
                # [Fix] 다양한 응답 필드 지원 (output, oso, ordr_list 등)
                raw_orders = result.get('output')
                if raw_orders is None: raw_orders = result.get('oso')
                if raw_orders is None: raw_orders = result.get('ordr_list')
                if raw_orders is None: raw_orders = []

                normalized_orders = []
                for o in raw_orders:
                    # [Fix] 키움 ka10075의 실제 필드명 매핑 (oso_qty, ord_pric, io_tp_nm 등)
                    # unex_qty 대신 oso_qty 가 미체결 수량임
                    unfilled_qty_str = str(o.get('oso_qty', o.get('unex_qty', '0'))).replace(',', '')
                    unfilled_qty = int(float(unfilled_qty_str)) if unfilled_qty_str else 0
                    
                    if unfilled_qty <= 0: 
                        continue # 체결 완료된 건 제외
                    
                    # io_tp_nm: 매수/매도 구분 (예: "매수", "매도", "+매수", "-매도")
                    io_tp = o.get('io_tp_nm', '')
                    # ord_tp가 있는 경우도 대비
                    ord_tp_val = str(o.get('ord_tp', ''))
                    is_buy = '매수' in io_tp or ord_tp_val == '01'
                    
                    normalized_orders.append({
                        'code': o.get('stk_cd', ''),
                        'stk_cd': o.get('stk_cd', ''),
                        'name': o.get('stk_nm', ''),
                        'qty': unfilled_qty,
                        'price': int(float(str(o.get('ord_pric', o.get('ord_unpr', 0))).replace(',',''))),
                        'ord_tp': '01' if is_buy else '02',
                        'type': 'buy' if is_buy else 'sell',
                        'ord_no': o.get('ord_no', ''),
                        'org_ord_no': o.get('orig_ord_no', o.get('org_ord_no', ''))
                    })
                
                if normalized_orders:
                    logger.info(f"[미체결 조회] {len(normalized_orders)}개 주문 확인")
                    return normalized_orders
                else:
                    return []
                return []
                    
            except Exception as e:
                logger.error(f"미체결 주문 조회 오류: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1.0)
                    continue
                return []
        
        return []
    
    
    def check_order_execution(self, ord_no: str, token: str) -> Dict:
        """
        주문 체결 상태 확인 (kt10005)
        
        Args:
            ord_no: 주문번호
            token: 인증 토큰
            
        Returns:
            {
                'status': 'completed' | 'pending' | 'cancelled' | 'rejected',
                'executed_qty': 체결 수량,
                'remaining_qty': 미체결 수량,
                'executed_price': 체결 가격,
                'order_time': 주문 시간,
                'executed_time': 체결 시간
            }
        """
        endpoint = '/api/dostk/ordr'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'kt10005',
        }
        
        if self.my_account:
            headers['cano'] = str(self.my_account)
        
        params = {
            'dmst_stex_tp': getattr(config, 'market_code', 'KRX'),
            'org_ord_no': ord_no,
        }
        
        try:
            response = requests.post(url, headers=headers, json=params, timeout=10)
            result = response.json()
            
            # 주문 상태 파싱
            order_data = result.get('output', result.get('ordr_info', {}))
            
            if not order_data:
                logger.warning(f"[체결 확인] 주문번호 {ord_no}: 조회 결과 없음")
                return {'status': 'unknown', 'executed_qty': 0, 'remaining_qty': 0}
            
            # 체결 상태 판단
            ord_status = order_data.get('ord_status', order_data.get('ORD_STATUS', ''))
            executed_qty = int(order_data.get('ctrct_qty', order_data.get('CTRCT_QTY', 0)))
            total_qty = int(order_data.get('ord_qty', order_data.get('ORD_QTY', 0)))
            remaining_qty = total_qty - executed_qty
            
            # 상태 매핑
            if ord_status in ['02', 'COMPLETED', '체결']:
                status = 'completed'
            elif ord_status in ['01', 'PENDING', '접수']:
                status = 'pending'
            elif ord_status in ['03', 'CANCELLED', '취소']:
                status = 'cancelled'
            elif ord_status in ['04', 'REJECTED', '거부']:
                status = 'rejected'
            else:
                status = 'unknown'
            
            # 부분 체결 처리
            if executed_qty > 0 and remaining_qty > 0:
                status = 'partial'
            
            execution_info = {
                'status': status,
                'executed_qty': executed_qty,
                'remaining_qty': remaining_qty,
                'executed_price': int(order_data.get('ctrct_prc', order_data.get('CTRCT_PRC', 0))),
                'order_time': order_data.get('ord_time', order_data.get('ORD_TIME', '')),
                'executed_time': order_data.get('ctrct_time', order_data.get('CTRCT_TIME', ''))
            }
            
            logger.info(f"[체결 확인] 주문번호 {ord_no}: {status} (체결: {executed_qty}/{total_qty})")
            return execution_info
            
        except Exception as e:
            logger.error(f"체결 확인 오류: {e}")
            return {'status': 'error', 'executed_qty': 0, 'remaining_qty': 0}
    
    def cancel_stock(self, stk_cd: str, qty: str, org_ord_no: str, token: str) -> Tuple[str, str]:
        """주문 취소"""
        endpoint = '/api/dostk/ordr'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'kt10003',
        }
        
        params = {
            'dmst_stex_tp': getattr(config, 'market_code', 'KRX'),
            'stk_cd': stk_cd,
            'cncl_qty': str(qty),
            'orig_ord_no': org_ord_no,
            'ord_uv': '0',
            'trde_tp': '0', 
            'cond_uv': '',
        }
        
        try:
            response = requests.post(url, headers=headers, json=params)
            result = response.json()
            logger.info(f"주문 취소 결과: {result}")
            return result.get('return_code', ''), result.get('return_msg', '')
        except Exception as e:
            logger.error(f"주문 취소 오류: {e}")
            return 'ERROR', str(e)

    def get_current_price(self, stk_cd: str, token: str) -> Optional[int]:
        """실시간 현재가 조회 (ka10004)"""
        endpoint = '/api/dostk/mrkcond'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'ka10004',
        }
        
        params = {
            'stk_cd': stk_cd,
        }
        
        try:
            response = requests.post(url, headers=headers, json=params, timeout=10)
            data = response.json()
            # sel_fpr_bid: 매도최우선호가
            price_raw = data.get('sel_fpr_bid', data.get('stk_prpr', '0'))
            price = abs(int(float(str(price_raw).replace(',', ''))))
            return price
        except Exception as e:
            logger.error(f"현재가 조회 오류: {e}")
            return None
    def get_trade_history(self, token: str) -> List[Dict]:
        """주식 일별 체결 내역 조회 (opw00007)"""
        if not token:
            return []
            
        # REST API에서는 보통 /api/dostk/acnt 엔드포인트에서 여러 조회를 처리함
        endpoint = '/api/dostk/acnt'
        url = self.host_url + endpoint
        
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'fn_opw00007', # 어댑터에서 기대하는 ID 또는 실제 키움 ID
        }
        
        if self.my_account:
            headers['cano'] = str(self.my_account)
            
        import datetime
        today = datetime.datetime.now().strftime('%Y%m%d')
        
        params = {
            'dmst_stex_tp': '0',   # 0: 전체
            'qry_tp': '0',         # 0: 전체
            'trde_tp': '0',        # 0: 전체
            'all_stk_tp': '0',     # 0: 전체
            'stex_tp': '0',        # 0: 전체
            'stk_cd': '',
            'qry_dt': today,       # 조회 일자
        }
        
        try:
            logger.info(f"[실전 데이터 연결] 키움 체결 내역 조회 시도 ({today})")
            response = requests.post(url, headers=headers, json=params, timeout=10)
            result = response.json()
            
            # 응답 필드 파싱 (출력 데이터는 output 또는 oso_history 등)
            raw_history = result.get('output', result.get('output1', []))
            if not isinstance(raw_history, list):
                raw_history = []
                
            history = []
            for item in raw_history:
                # 데이터 정규화 (로컬 DB 형식과 최대한 맞춤)
                stk_cd = item.get('stk_cd', '')
                qty_str = str(item.get('ctrct_qty', item.get('qty', '0'))).replace(',', '')
                price_str = str(item.get('ctrct_prc', item.get('avg_prc', '0'))).replace(',', '')
                
                try:
                    qty = int(float(qty_str))
                    price = int(float(price_str))
                    if qty <= 0: continue
                    
                    io_tp = item.get('io_tp_nm', '') # 매수/매도 구분
                    is_buy = '매수' in io_tp
                    
                    history.append({
                        'time': item.get('ord_dt', today) + " " + item.get('ord_tm', '000000'),
                        'type': 'buy' if is_buy else 'sell',
                        'stk_cd': stk_cd,
                        'stk_nm': item.get('stk_nm', ''),
                        'qty': qty,
                        'price': price,
                        'amt': qty * price,
                        'mode': 'REAL'
                    })
                except:
                    continue
            
            logger.info(f"[실전 데이터 연결] 실제 계좌 체결 {len(history)}건 확인됨")
            return history
            
        except Exception as e:
            logger.error(f"실전 체결 내역 조회 오류: {e}")
            return []
