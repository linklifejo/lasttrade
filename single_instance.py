import os
import sys

class SingleInstance:
	"""프로그램의 중복 실행을 방지하는 클래스"""
	
	def __init__(self, lockfile):
		self.lockfile = lockfile
		self.fp = None
		
	def __enter__(self):
		"""컨텍스트 매니저 진입 시 락 파일 생성"""
		if os.path.exists(self.lockfile):
			# 락 파일이 존재하면 PID 확인
			try:
				with open(self.lockfile, 'r') as f:
					old_pid = int(f.read().strip())
				
				# 해당 PID의 프로세스가 실행 중인지 확인
				if self._is_process_running(old_pid):
					print(f"프로그램이 이미 실행 중입니다 (PID: {old_pid})")
					print("기존 프로그램을 종료하거나 락 파일을 삭제하세요:")
					print(f"  {self.lockfile}")
					sys.exit(1)
				else:
					# 프로세스가 실행 중이 아니면 락 파일 삭제
					print(f"이전 프로세스(PID: {old_pid})가 비정상 종료되었습니다. 락 파일을 정리합니다.")
					os.remove(self.lockfile)
			except (ValueError, FileNotFoundError):
				# 락 파일이 손상되었으면 삭제
				if os.path.exists(self.lockfile):
					os.remove(self.lockfile)
		
		# 현재 PID를 락 파일에 기록
		self.fp = open(self.lockfile, 'w')
		self.fp.write(str(os.getpid()))
		self.fp.flush()
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		"""컨텍스트 매니저 종료 시 락 파일 삭제"""
		if self.fp:
			self.fp.close()
		if os.path.exists(self.lockfile):
			os.remove(self.lockfile)
	
	def _is_process_running(self, pid):
		"""주어진 PID의 프로세스가 실행 중인지 확인"""
		try:
			# Windows
			if sys.platform == 'win32':
				import ctypes
				kernel32 = ctypes.windll.kernel32
				PROCESS_QUERY_INFORMATION = 0x0400
				handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
				if handle:
					kernel32.CloseHandle(handle)
					return True
				return False
			# Unix/Linux
			else:
				os.kill(pid, 0)
				return True
		except (OSError, AttributeError):
			return False
