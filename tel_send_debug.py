import requests
import json
import sys
from database_helpers import get_setting
from logger import logger

def tel_send(message):
    token = get_setting('telegram_token')
    chat_id = get_setting('telegram_chat_id')
    process_name = get_setting('process_name', '')
    
    if not token or not chat_id:
        print("❌ 텔레그램 설정이 없습니다. (Token 또는 Chat ID 누락)")
        logger.warning("텔레그램 설정 누락")
        return None

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": f"[{process_name}] {message}" 
    }

    try:
        print(f"전송 시도: {url[:35]}... (ID: {chat_id})")
        response = requests.post(url, json=data, timeout=5) # 5초 타임아웃
        result = response.json()
        
        if result.get('ok'):
            print("✅ 전송 성공!")
            logger.debug(f"텔레그램 메시지 전송 성공: {message[:50]}...")
        else:
            print(f"❌ 전송 실패: {result}")
            logger.error(f"텔레그램 메시지 전송 실패: {result}")
        return result
        
    except requests.Timeout:
        print("❌ 타임아웃 발생 (서버 응답 없음)")
        logger.error(f"텔레그램 메시지 전송 타임아웃")
        return None
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        logger.error(f"텔레그램 메시지 전송 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "키움 API 테스트 메시지"
    print(f"메시지 전송 테스트: '{msg}'")
    tel_send(msg)
