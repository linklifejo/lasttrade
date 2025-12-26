import os
import sys
import subprocess
import time
import webbrowser

# [설정] 실행할 스크립트
WEB_SERVER_SCRIPT = "web_server.py"

# stop.py의 강력한 종료 기능을 가져옵니다 (종료 시에만 사용)
def cleanup_before_start():
    """시작 전 간단한 정리 (빠른 실행)"""
    print("[+] Cleaning up previous processes...", end="", flush=True)
    # 이전 봇 프로세스만 빠르게 정리
    os.system('wmic process where "commandline like \'%%web_server.py%%\'" delete >nul 2>&1')
    os.system('wmic process where "commandline like \'%%watchdog.py%%\'" delete >nul 2>&1')
    print(" Done.")


def run_system():
    """서버와 봇(web_server.py) 실행"""
    print(f"[+] Starting Kiwoom Bot System...", end="", flush=True)
    
    python_exe = sys.executable
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), WEB_SERVER_SCRIPT)
    
    # 웹 서버(및 내장된 봇)를 새로운 콘솔 창에서 실행
    # [수정] Agent 환경 디버깅을 위해 콘솔 분리 옵션 제거 및 현재 프로세스에 연결
    proc = subprocess.Popen(
        [python_exe, script_path], 
        cwd=os.path.dirname(script_path)
        # creationflags=subprocess.CREATE_NEW_CONSOLE # 제거
    )
    print(" Done.")
    return proc

def open_browser():
    """브라우저에서 대시보드 열기 (이미 열려있으면 새 탭 사용)"""
    import urllib.request
    import urllib.error
    
    print("[+] Waiting for server...", end="", flush=True)
    time.sleep(3)  # 서버 초기화 대기
    
    # 서버가 응답하는지 확인
    max_retries = 10
    for i in range(max_retries):
        try:
            urllib.request.urlopen("http://localhost:8080", timeout=1)
            print(" Ready!", flush=True)
            break
        except:
            if i < max_retries - 1:
                time.sleep(1)
            else:
                print(" Timeout.", flush=True)
                return
    
    # 새 탭으로 열기 (기존 창 유지)
    url = "http://localhost:8080"
    webbrowser.open(url, new=2)  # new=2: 새 탭
    print("[+] Dashboard opened in browser")

if __name__ == "__main__":
    print(f"🚀 Kiwoom Auto Trading System Launcher")
    print("========================================")
    
    # 1. 시작 전 청소 (좀비 프로세스 정리)
    cleanup_before_start()
    
    time.sleep(1)
    
    # 2. 시스템 시작
    system_process = run_system()
    
    # 3. 브라우저 열기
    open_browser()
    
    print("\n✅ System started successfully.")
    print("📊 Dashboard: http://localhost:8080")
    print("💡 Press Ctrl+C in this window to STOP ALL systems safely.")
    
    try:
        # 4. 메인 루프
        while True:
            time.sleep(1)
            if system_process.poll() is not None:
                print("\n⚠️ System process ended unexpectedly.")
                break
                
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping system requested by user...")
    
    finally:
        # 5. 종료 시 자동 청소
        print("🧹 Performing safe shutdown...")
        try:
            if system_process.poll() is None:
                system_process.terminate()
                time.sleep(0.5)  # 프로세스 종료 대기
        except: 
            pass
        
        # stop.py 호출로 최종 정리 (동기 실행)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        stop_script = os.path.join(script_dir, 'stop.py')
        
        print("🧹 Running cleanup script...")
        try:
            # 동기적으로 실행하여 완전히 종료될 때까지 대기
            result = subprocess.run(
                [sys.executable, stop_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            # stop.py의 출력 표시
            if result.stdout:
                print(result.stdout)
        except subprocess.TimeoutExpired:
            print("⚠️ Cleanup timeout - forcing exit")
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
        
        print("👋 Bye!")
        sys.exit(0)

