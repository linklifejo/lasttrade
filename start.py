import os
import sys
import subprocess
import time
import webbrowser

# [설정] 실행할 스크립트
WEB_SERVER_SCRIPT = "web_server.py"
BOT_SCRIPT = "bot.py"

# stop.py의 강력한 종료 기능을 가져옵니다 (종료 시에만 사용)
def cleanup_before_start():
    """시작 전 간단한 정리 (빠른 실행)"""
    print("[+] Cleaning up previous processes...", end="", flush=True)
    # 이전 프로세스들을 확실히 정리
    os.system('wmic process where "commandline like \'%%web_server.py%%\'" delete >nul 2>&1')
    os.system('wmic process where "commandline like \'%%bot.py%%\'" delete >nul 2>&1')
    os.system('wmic process where "commandline like \'%%watchdog.py%%\'" delete >nul 2>&1')
    
    # [New] 기존 락 파일 정리
    for lock in ['main.lock', 'web.lock']:
        if os.path.exists(lock):
            try: os.remove(lock)
            except: pass
    print(" Done.")
    
    


def run_system():
    """서버와 봇을 각각 별도 콘솔 창에서 실행"""
    python_exe = sys.executable
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    server_path = os.path.join(script_dir, WEB_SERVER_SCRIPT)
    bot_path = os.path.join(script_dir, BOT_SCRIPT)
    
    print(f"[+] Starting Mock Server...", end="", flush=True)
    server_proc = subprocess.Popen(
        [python_exe, server_path], 
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print(" Done.")
    
    time.sleep(1)
    
    print(f"[+] Starting Trading Engine...", end="", flush=True)
    bot_proc = subprocess.Popen(
        [python_exe, bot_path], 
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print(" Done.")
    
    return server_proc, bot_proc

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
    server_process, bot_process = run_system()
    
    # 3. 브라우저 열기
    open_browser()
    
    print("\n✅ System started successfully.")
    print("📊 Dashboard: http://localhost:8080")
    print("💡 Press Ctrl+C in this window to STOP ALL systems safely.")
    
    try:
        # 4. 메인 루프 (두 프로세스 모두 모니터링)
        print("\n⏳ Monitoring processes (5s grace period)...")
        time.sleep(5) # 윈도우 심(Shim) 프로세스 종료 대기 시간

        while True:
            time.sleep(5)
            # 서버 프로세스 체크
            if server_process.poll() is not None:
                # 윈도우 환경에서는 프로세스가 살아있어도 poll이 리턴될 수 있으므로 한 번 더 확인
                print("\n⚠️ Mock Server process status changed. Checking stability...")
                time.sleep(2)
                if server_process.poll() is not None:
                    # 실제 종료됨
                    # print("\n⚠️ Mock Server process ended.")
                    # break (일단 창이 떠있으면 계속 유지하도록 처리 가능하나, 여기서는 브레이크 유지)
                    pass 

            if bot_process.poll() is not None:
                # 엔진도 동일하게 체크
                pass
                
        # [수정] 런처가 꺼져도 실제 봇 창은 살아있게 하려면 여기서 대기
        # print("\n💡 Launcher is now in monitoring mode. Press Ctrl+C to stop all.")
        # while True: time.sleep(100)
                
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping system requested by user...")
    
    finally:
        # 5. 종료 시 자동 청소
        print("🧹 Performing safe shutdown...")
        for proc in [server_process, bot_process]:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except: pass
        
        time.sleep(1)
        
        # stop.py 호출로 최종 정리 (동기 실행)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        stop_script = os.path.join(script_dir, 'stop.py')
        
        print("🧹 Running cleanup script...")
        try:
            result = subprocess.run(
                [sys.executable, stop_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.stdout:
                print(result.stdout)
        except subprocess.TimeoutExpired:
            print("⚠️ Cleanup timeout - forcing exit")
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
        
        print("👋 Bye!")
        sys.exit(0)

