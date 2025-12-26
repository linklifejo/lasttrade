import subprocess
import sys
import time
import os
from datetime import datetime
try:
    from tel_send import tel_send
except ImportError:
    def tel_send(msg): print(f"[No Telegram] {msg}")

# 감시할 대상 스크립트
TARGET_SCRIPT = "web_server.py"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] [WATCHDOG] {msg}"
    print(full_msg)
    return full_msg

def run_zombie():
    python_exe = sys.executable
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), TARGET_SCRIPT)
    
    start_msg = log(f"🔥 좀비 모드(Watchdog) 시작: {TARGET_SCRIPT} 감시 중...")
    tel_send(start_msg)
    
    while True:
        try:
            # 1. 프로세스 실행 (새 콘솔 창 출력)
            log(f"프로세스 실행 중: {TARGET_SCRIPT}")
            process = subprocess.Popen(
                [python_exe, script_path],
                cwd=os.path.dirname(script_path), # CWD 명시
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            # 2. 감시 루프 (Heartbeat)
            log("1분 주기로 생존 신고를 합니다. (눈 뜨고 감시 중 👀)")
            while True:
                exit_code = process.poll()
                if exit_code is not None:
                    # 프로세스 종료됨
                    break
                
                # 봇은 살아있음. 1분 대기하면서 감시
                for _ in range(60):
                    if process.poll() is not None: break
                    
                    # [센스: 프리징 감지] 프로세스는 살아있는데 데이터 갱신이 멈췄는지 체크
                    try:
                        # [DB 기반 감시로 전환] status.json 대신 DB의 system_status 테이블 확인
                        import sqlite3
                        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trading.db")
                        if os.path.exists(db_path):
                            with sqlite3.connect(db_path, timeout=5) as conn:
                                conn.row_factory = sqlite3.Row
                                cursor = conn.execute('SELECT updated_at FROM system_status WHERE id = 1')
                                row = cursor.fetchone()
                                if row:
                                    updated_at = datetime.strptime(row['updated_at'], '%Y-%m-%d %H:%M:%S')
                                    diff = (datetime.now() - updated_at).total_seconds()
                                    
                                    # 장 시간(09:00~15:40)이고, 마지막 DB 갱신 후 180초(3분) 지났다면 먹통으로 간주
                                    now_time = datetime.now().hour * 100 + datetime.now().minute
                                    if 900 <= now_time <= 1540 and diff > 180:
                                        log(f"🚨 [프로세스 프리징 감지] DB 상태가 {int(diff)}초 동안 갱신되지 않음!")
                                        tel_send(f"🚨 봇이 응답하지 않아(Freezing) 강제 재시작합니다. ({int(diff)}초 미갱신)")
                                        process.terminate()
                                        break
                    except Exception as e:
                        pass
                    
                    time.sleep(1)
                
                if process.poll() is None:
                    timestamp = datetime.now().strftime("%H:%M")
                    print("\n" + "="*40)
                    print(f"[{timestamp}] [WATCHDOG] 👮 이상 무! 봇이 열심히 매매 중입니다.")
                    print("="*40 + "\n")

            # 3. 종료 감지 및 알림
            crash_msg = f"⚠️ 봇 프로세스 종료 감지! (Code: {exit_code})"
            log(crash_msg)
            tel_send(crash_msg)
            
            if exit_code != 0:
                tel_send("🚨 비정상 종료 발생! 로그를 확인하세요.")
            
            # 4. 재시작 대기
            retry_msg = "♻️ 5초 후 봇을 재가동합니다..."
            log(retry_msg)
            tel_send(retry_msg)
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            stop_msg = "🛑 사용자 요청으로 좀비 모드를 종료합니다."
            log(stop_msg)
            tel_send(stop_msg)
            if 'process' in locals() and process:
                process.terminate()
            break
        except Exception as e:
            err_msg = f"☠️ Watchdog 치명적 오류: {e}"
            log(err_msg)
            tel_send(err_msg)
            time.sleep(5)

if __name__ == "__main__":
    run_zombie()
