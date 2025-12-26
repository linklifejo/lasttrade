import requests
import json
from config import host_url
from login import fn_au10001 as get_token
from get_setting import get_setting
from logger import logger

# 주식기본정보요청
def fn_ka10001(stk_cd, cont_yn='N', next_key='', token=None):
	# [Mock Server Support] Mock 모드 체크
	use_mock = get_setting('use_mock_server', False)
	
	if use_mock:
		try:
			# Mock 데이터 로드 (stocks.json)
			import os
			base_dir = os.path.dirname(os.path.abspath(__file__))
			stocks_file = os.path.join(base_dir, 'kiwoom', 'mock_data', 'stocks.json')
			
			if os.path.exists(stocks_file):
				with open(stocks_file, 'r', encoding='utf-8') as f:
					stocks = json.load(f)
					if stk_cd in stocks:
						name = stocks[stk_cd]['name']
						# logger.info(f"🎮 Mock 종목정보 조회: {name}({stk_cd})")
						return name
			
			logger.warning(f"🎮 Mock 종목정보 없음: {stk_cd}")
			return stk_cd # 검색 실패 시 코드를 이름 대신 반환
		except Exception as e:
			logger.error(f"🎮 Mock 종목정보 조회 오류: {e}")
			return stk_cd

	# 실제 모드: 기존 API 호출
	endpoint = '/api/dostk/stkinfo'
	url =  host_url + endpoint

	headers = {
		'Content-Type': 'application/json;charset=UTF-8', # 컨텐츠타입
		'authorization': f'Bearer {token}', # 접근토큰
		'cont-yn': cont_yn, # 연속조회여부
		'next-key': next_key, # 연속조회키
		'api-id': 'ka10001', # TR명
	}

	params = {
		'stk_cd': stk_cd, # 종목코드
	}

	try:
		response = requests.post(url, headers=headers, json=params)
		return response.json()['stk_nm']
	except Exception as e:
		logger.error(f"주식정보 조회 실패: {e}")
		return stk_cd

# 실행 구간
if __name__ == '__main__':
	print(fn_ka10001('005930', token=get_token()))