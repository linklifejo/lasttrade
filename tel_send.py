import requests
import json
from get_setting import get_setting
from config import telegram_token, telegram_chat_id
from logger import logger

def tel_send(message):
	url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"

	data = {
		"chat_id": telegram_chat_id,
		"text": f"[{get_setting('process_name', '')}] {message}" 
	}

	try:
		response = requests.post(url, json=data, timeout=10)
		result = response.json()
		if result.get('ok'):
			logger.debug(f"텔레그램 메시지 전송 성공: {message[:50]}...")
		else:
			logger.error(f"텔레그램 메시지 전송 실패: {result}")
		return result
	except requests.Timeout:
		logger.error(f"텔레그램 메시지 전송 타임아웃: {message[:50]}...")
		return None
	except Exception as e:
		logger.error(f"텔레그램 메시지 전송 중 오류 발생: {e}", exc_info=True)
		return None

if __name__ == "__main__":
	tel_send("키움 API 테스트")