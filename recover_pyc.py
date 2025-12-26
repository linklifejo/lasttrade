import sys
import marshal
import dis

# .pyc 파일 읽기
with open('__pycache__/check_n_buy.cpython-39.pyc', 'rb') as f:
    # 헤더 스킵 (Python 3.7+는 16바이트)
    f.read(16)
    # 코드 객체 로드
    code = marshal.load(f)

# 디스어셈블리 출력
print("# Recovered from .pyc file")
print("# This is a decompiled version - may need manual fixes")
print()
dis.dis(code)
