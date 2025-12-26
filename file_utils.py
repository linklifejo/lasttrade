"""
안전한 파일 작업 유틸리티
"""
import json
import os
import time
from logger import logger


def safe_write_json(filepath, data, max_retries=3, retry_delay=0.1):
    """
    JSON 파일을 안전하게 작성합니다.
    파일 잠금 오류 발생 시 재시도합니다.
    
    Args:
        filepath (str): 파일 경로
        data (dict): 저장할 데이터
        max_retries (int): 최대 재시도 횟수
        retry_delay (float): 재시도 간격 (초)
        
    Returns:
        bool: 성공 여부
    """
    for attempt in range(max_retries):
        try:
            # 임시 파일에 먼저 쓰기
            temp_file = f"{filepath}.tmp"
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 원자적 교체 (Windows에서는 먼저 삭제 필요)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except PermissionError:
                    # 다른 프로세스가 파일을 사용 중
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise
            
            os.rename(temp_file, filepath)
            return True
            
        except PermissionError as e:
            if attempt < max_retries - 1:
                logger.warning(f"File write failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                logger.error(f"File write failed after {max_retries} attempts: {filepath} - {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error writing JSON file {filepath}: {e}")
            return False
    
    return False


def safe_read_json(filepath, default=None):
    """
    JSON 파일을 안전하게 읽습니다.
    
    Args:
        filepath (str): 파일 경로
        default: 파일이 없거나 오류 시 반환할 기본값
        
    Returns:
        dict: JSON 데이터 또는 기본값
    """
    try:
        if not os.path.exists(filepath):
            return default if default is not None else {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {filepath}: {e}")
        return default if default is not None else {}
    except Exception as e:
        logger.error(f"Error reading JSON file {filepath}: {e}")
        return default if default is not None else {}
