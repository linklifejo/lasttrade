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

from voice_generator import speak

# [AI Guardian] 감시 설정
TARGET_SCRIPT = "bot.py"
ERROR_LOG_DIR = "logs"
DB_FILE = "trading.db"
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
TIMEOUT_SEC = 60  # 60초 동안 소식 없으면 사망 판정 (기존 20초 -> 60초로 완화)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] [WATCHDOG] {msg}"
    print(full_msg)
    return full_msg

def analyze_error():
    """최신 에러 로그를 분석하여 원인을 유추합니다."""
    try:
        today_str = datetime.now().strftime("%Y%m%d")
        error_file = os.path.join(ERROR_LOG_DIR, f"error_bot_{today_str}.log")
        if os.path.exists(error_file):
            with open(error_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    # 마지막 에러 블록 추출 (최대 10줄)
                    last_error = lines[-10:]
                    return "".join(last_error).strip()
    except: pass
    return "상세 원인을 파악할 수 없는 시스템 오류입니다."

def perform_maintenance():
    """시스템 자가 유지보수 (DB 최적화 및 로그 정리)"""
    log("🛠️ [AI Maintenance] 시스템 정기 유지보수를 시작합니다.")
    speak("시스템 정기 점검 시간입니다. 데이터베이스를 최적화하고 로그를 정리하겠습니다.")
    
    # 1. DB 최적화 (VACUUM)
    try:
        import sqlite3
        conn = sqlite3.connect(DB_FILE)
        conn.execute("VACUUM")
        conn.close()
        log("✅ DB 최적화 완료 (VACUUM)")
    except Exception as e:
        log(f"⚠️ DB 최적화 실패: {e}")
        
    # 2. 오래된 로그 정리 (30일 이상)
    try:
        import glob
        now = time.time()
        for f in glob.glob(os.path.join(ERROR_LOG_DIR, "*.log*")):
            if os.stat(f).st_mtime < now - (30 * 86400):
                os.remove(f)
        log("✅ 30일 경과 로그 정리 완료")
    except Exception as e:
        log(f"⚠️ 로그 정리 실패: {e}")

    speak("정기 점검을 마쳤습니다. 엔진을 깨끗한 상태로 재가동합니다.")

def run_watchdog():
    python_exe = sys.executable
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), TARGET_SCRIPT)
    
    start_msg = log(f"🤖 [AI Guardian] 엔진 감시 시스템을 가동합니다. 심장 박동을 체크합니다.")
    speak("에이아이 가디언 시스템을 가동합니다. 엔진의 상태를 실시간으로 모니터링하겠습니다.")
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
                # [365 Maintenance Check] 매일 새벽 4시에 유지보수 후 엔진 재시작
                now_dt = datetime.now()
                if now_dt.hour == 4 and now_dt.minute == 0 and 0 <= now_dt.second <= 5:
                    log("⏰ 정기 점검 시각 도달. 엔진을 안전하게 재시작합니다.")
                    process.terminate()
                    perform_maintenance()
                    break # 재시작 루프로 이동

                # 프로세스가 이미 죽었는지 체크
                if process.poll() is not None:
                    exit_code = process.poll()
                    if exit_code == 0:
                        log(f"✅ 엔진이 종료되었습니다. (365 관리 모드: 자동 재기동)")
                        speak("엔진이 업무를 마쳤으나, 365 상시 관리 원칙에 따라 즉시 재가동하겠습니다.")
                        # return 대신 break로 가서 무한 재시작
                        break 
                    else:
                        error_detail = analyze_error()
                        log(f"⚠️ 엔진이 비정상 종료되었습니다! (Code: {exit_code})\n사유: {error_detail}")
                        speak(f"경고. 엔진이 비정상적으로 종료되었습니다. 원인은 다음과 같습니다. {error_detail[:50]}. 가디언이 즉시 복구하겠습니다.")
                        tel_send(f"⚠️ 봇 크래시 발생! 사유: {error_detail[:200]}")
                        break # 재시작 루프로 이동
                
                try:
                    # UDP 패킷 수신 대기 (Blocking with Timeout)
                    data, addr = sock.recvfrom(1024)
                    try:
                        hb = json.loads(data.decode())
                        if hb.get("status") == "alive":
                            error_count = 0
                    except json.JSONDecodeError:
                        pass
                        
                except socket.timeout:
                    log(f"🚨 [심정지 경보] {TIMEOUT_SEC}초 동안 엔진 응답 없음!")
                    speak("심정지 경보 발생. 엔진이 응답하지 않습니다. 가디언이 강제 심폐소생술을 실시합니다.")
                    tel_send(f"🚨 봇 응답 없음(Freezing)! AI Guardian이 재시작을 강행합니다.")
                    
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
