import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger(name='trading_bot', log_dir='logs'):
	"""
	로깅 시스템을 설정합니다.
	
	Args:
		name: 로거 이름
		log_dir: 로그 파일을 저장할 디렉토리
	
	Returns:
		logging.Logger: 설정된 로거 객체
	"""
	# 로그 디렉토리 생성
	script_dir = os.path.dirname(os.path.abspath(__file__))
	log_path = os.path.join(script_dir, log_dir)
	os.makedirs(log_path, exist_ok=True)
	
	# 로거 생성
	logger = logging.getLogger(name)
	logger.setLevel(logging.DEBUG)
	
	# 이미 핸들러가 있으면 제거 (중복 방지)
	if logger.handlers:
		logger.handlers.clear()
	
	# 포맷 설정
	formatter = logging.Formatter(
		'%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		datefmt='%Y-%m-%d %H:%M:%S'
	)
	
	# 1. 파일 핸들러 (일반 로그) - 최대 10MB, 5개 파일 로테이션
	today = datetime.now().strftime('%Y%m%d')
	file_handler = RotatingFileHandler(
		os.path.join(log_path, f'trading_{today}.log'),
		maxBytes=10*1024*1024,  # 10MB
		backupCount=5,
		encoding='utf-8'
	)
	file_handler.setLevel(logging.DEBUG)
	file_handler.setFormatter(formatter)
	logger.addHandler(file_handler)
	
	# 2. 파일 핸들러 (에러 로그만)
	error_handler = RotatingFileHandler(
		os.path.join(log_path, f'error_{today}.log'),
		maxBytes=10*1024*1024,  # 10MB
		backupCount=5,
		encoding='utf-8'
	)
	error_handler.setLevel(logging.ERROR)
	error_handler.setFormatter(formatter)
	logger.addHandler(error_handler)
	
	# 3. 콘솔 핸들러 (INFO 레벨 이상만 출력)
	console_handler = logging.StreamHandler()
	console_handler.setLevel(logging.INFO)
	console_handler.setFormatter(formatter)
	logger.addHandler(console_handler)
	
	return logger

# 전역 로거 인스턴스
logger = setup_logger()
