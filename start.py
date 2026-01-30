import os
import sys
import subprocess
import time
import webbrowser

# [설정] 실행할 스크립트
WEB_SERVER_SCRIPT = "web_server.py"
BOT_SCRIPT = "bot.py"
WATCHDOG_SCRIPT = "watchdog.py"

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
    """서버와 워치독을 각각 별도 콘솔 창에서 실행 (봇은 워치독이 실행함)"""
    python_exe = sys.executable
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    server_path = os.path.join(script_dir, WEB_SERVER_SCRIPT)
    
    print(f"[+] Starting Web Dashboard...", end="", flush=True)
    server_proc = subprocess.Popen(
        [python_exe, server_path], 
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print(" Done.")
    
    time.sleep(1)
    
    print(f"[+] Starting Watchdog (Heartbeat Guardian)...", end="", flush=True)
    watchdog_path = os.path.join(script_dir, WATCHDOG_SCRIPT)
    wd_proc = subprocess.Popen(
        [python_exe, watchdog_path],
        cwd=script_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print(" Done.")
    
    return server_proc, wd_proc

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
    server_process, wd_process = run_system()
    
    # 3. 브라우저 열기
    open_browser()
    
    print("\n✅ System started successfully.")
    print("📊 Dashboard: http://localhost:8080")
    print("💡 Press Ctrl+C in this window to STOP ALL systems safely.")
    
    try:
        # 4. 프로세스 상태 확인 (5초 딜레이)
        print("\n⏳ Verifying startup (5s)...")
        time.sleep(5)
        
        server_alive = server_process.poll() is None
        wd_alive = wd_process.poll() is None
        
        if server_alive and wd_alive:
            print("✅ All systems operational.")
            print("👋 Launcher exiting... (Services run in background)")
            sys.exit(0)
        else:
            print("❌ Some services failed to start.")
            if not server_alive: print("   - Web Server failed")
            if not wd_alive: print("   - Watchdog failed")
            
    except KeyboardInterrupt:
        print("\n\n🛑 Start aborted.")
        
    # Launcher가 종료되어도 자식 프로세스는 CREATE_NEW_CONSOLE로 독립 실행 중이므로 유지됨

