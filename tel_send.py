import requests
import json
import threading
from get_setting import get_setting
from logger import logger

def _send_thread(message):
    """실제 전송을 담당하는 스레드 함수"""
    try:
        token = get_setting('telegram_token')
        chat_id = get_setting('telegram_chat_id')
        process_name = get_setting('process_name', '')
        
        if not token or not chat_id:
            logger.warning("텔레그램 설정이 없습니다.")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"

        data = {
            "chat_id": chat_id,
            "text": f"[{process_name}] {message}" 
        }

        # 타임아웃 3초 (빠른 실패)
        response = requests.post(url, json=data, timeout=3)
        result = response.json()
        
        if not result.get('ok'):
            logger.error(f"텔레그램 전송 실패: {result}")
            
    except Exception as e:
        logger.error(f"텔레그램 전송 오류: {e}")

def tel_send(message):
    """
    메시지를 비동기(스레드)로 전송합니다.
    호출 즉시 리턴하므로 메인 로직이 차단되지 않습니다.
    """
    try:
        t = threading.Thread(target=_send_thread, args=(message,), daemon=True)
        t.start()
        return True
    except Exception as e:
        logger.error(f"텔레그램 스레드 시작 실패: {e}")
        return False

if __name__ == "__main__":
    tel_send("비동기 전송 테스트입니다.")
    import time
    time.sleep(1) # 스레드 실행 대기