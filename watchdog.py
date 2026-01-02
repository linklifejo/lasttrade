import subprocess
import sys
import time
import os
import socket
import json
from datetime import datetime

try:
    from tel_send import tel_send
except ImportError:
    def tel_send(msg): print(f"[No Telegram] {msg}")

# 감시 설정
TARGET_SCRIPT = "bot.py"
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
TIMEOUT_SEC = 60  # 60초 동안 소식 없으면 사망 판정 (기존 20초 -> 60초로 완화)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] [WATCHDOG] {msg}"
    print(full_msg)
    return full_msg

def run_watchdog():
    python_exe = sys.executable
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), TARGET_SCRIPT)
    
    start_msg = log(f"🐕 [Socket Watchdog] 시작! {TARGET_SCRIPT}의 심장 박동(UDP {UDP_PORT})을 감시합니다.")
    tel_send(start_msg)
    
    # 1. 소켓 준비 (귀 열기)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(TIMEOUT_SEC) # 타임아웃 설정 (핵심)
    
    while True:
        try:
            # 2. 프로세스 실행
            log(f"🚀 엔진({TARGET_SCRIPT}) 시동을 겁니다...")
            process = subprocess.Popen(
                [python_exe, script_path],
                cwd=os.path.dirname(script_path),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            # 3. 감시 루프 (Heartbeat Listening)
            log(f"👂 엔진 소리를 듣고 있습니다... (Timeout: {TIMEOUT_SEC}초)")
            
            error_count = 0
            
            while True:
                # 프로세스가 이미 죽었는지 체크
                if process.poll() is not None:
                    exit_code = process.poll()
                    if exit_code == 0:
                        log(f"✅ 엔진이 정상 종료되었습니다. (Code: 0)")
                        return # 정상 종료 시 워치독도 퇴근
                    else:
                        log(f"⚠️ 엔진이 비정상 종료(Crash)되었습니다! (Code: {exit_code})")
                        tel_send(f"⚠️ 봇 크래시 발생! (Code: {exit_code})")
                        break # 재시작 루프로 이동
                
                try:
                    # UDP 패킷 수신 대기 (Blocking with Timeout)
                    data, addr = sock.recvfrom(1024)
                    try:
                        hb = json.loads(data.decode())
                        if hb.get("status") == "alive":
                            # 생존 확인!
                            error_count = 0
                            # 너무 자주 로그 찍으면 시끄러우니 가끔만 출력 (옵션)
                            # print(".", end="", flush=True) 
                            pass
                    except json.JSONDecodeError:
                        pass # 깨진 패킷은 무시
                        
                except socket.timeout:
                    # 타임아웃 발생! -> 심장 정지
                    log(f"🚨 [심정지 경보] {TIMEOUT_SEC}초 동안 엔진 신호가 없습니다! Freezing 감지!")
                    tel_send(f"🚨 봇 응답 없음(Freezing)! 강제 재시작합니다.")
                    
                    # 강제 종료
                    try: process.terminate()
                    except: pass
                    break # 재시작
                except Exception as e:
                    log(f"⚡ 소켓 에러: {e}")
                    time.sleep(1)
            
            # 4. 재시작 전 대기
            log("♻️ 5초 후 엔진을 재가동합니다...")
            time.sleep(5)
            
            # 소켓 비우기 (쌓인 구형 패킷 제거)
            try:
                sock.setblocking(0)
                while True:
                    sock.recv(1024)
            except:
                sock.settimeout(TIMEOUT_SEC) # 다시 타임아웃 모드로 복구
            
        except KeyboardInterrupt:
            log("🛑 사용자 요청으로 감시를 종료합니다.")
            if 'process' in locals() and process:
                process.terminate()
            break
        except Exception as e:
            msg = f"☠️ Watchdog 내부 오류: {e}"
            log(msg)
            tel_send(msg)
            time.sleep(5)
            
    sock.close()

if __name__ == "__main__":
    run_watchdog()
