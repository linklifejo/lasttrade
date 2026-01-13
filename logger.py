import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger(name='trading_bot', log_dir='logs'):
	"""
	로깅 시스템을 설정합니다. 
	윈도우에서 여러 프로세스가 하나의 로그 파일에 접근할 때 발생하는 PermissionError를 방지하기 위해 
	실행 파일 이름별로 로그 파일을 분리합니다.
	"""
	# 로그 디렉토리 생성
	script_dir = os.path.dirname(os.path.abspath(__file__))
	log_path = os.path.join(script_dir, log_dir)
	os.makedirs(log_path, exist_ok=True)
	
	# 실행 중인 스크립트 이름 파악 (예: bot, web_server, watchdog)
	main_script = os.path.basename(sys.argv[0]).replace('.py', '')
	if not main_script or main_script == 'ipykernel_launcher':
		main_script = 'trading'
	
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
	
	# 1. 파일 핸들러 (일반 로그) - 프로세스별로 이름 분리!
	today = datetime.now().strftime('%Y%m%d')
	log_filename = f'{main_script}_{today}.log'
	
	file_handler = RotatingFileHandler(
		os.path.join(log_path, log_filename),
		maxBytes=10*1024*1024,  # 10MB
		backupCount=5,
		encoding='utf-8'
	)
	file_handler.setLevel(logging.DEBUG)
	file_handler.setFormatter(formatter)
	logger.addHandler(file_handler)
	
	# 2. 파일 핸들러 (에러 로그)
	error_handler = RotatingFileHandler(
		os.path.join(log_path, f'error_{main_script}_{today}.log'),
		maxBytes=10*1024*1024,  # 10MB
		backupCount=5,
		encoding='utf-8'
	)
	error_handler.setLevel(logging.ERROR)
	error_handler.setFormatter(formatter)
	logger.addHandler(error_handler)
	
	# 3. 콘솔 핸들러
	console_handler = logging.StreamHandler()
	console_handler.setLevel(logging.INFO)
	console_handler.setFormatter(formatter)
	logger.addHandler(console_handler)
	
	return logger

# 전역 로거 인스턴스
logger = setup_logger()
