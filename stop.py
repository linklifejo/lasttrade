import os
import time
import subprocess

def kill_everything():
    """봇 관련 프로세스를 종료합니다."""
    print("🛑 Stopping all bot processes...", flush=True)
    
    try:
        # 1. 봇 관련 Python 프로세스 종료
        print("[-] Killing bot processes...", end="", flush=True)
        os.system('wmic process where "commandline like \'%%web_server.py%%\'" delete >nul 2>&1')
        os.system('wmic process where "commandline like \'%%watchdog.py%%\'" delete >nul 2>&1')
        os.system('wmic process where "commandline like \'%%start.py%%\'" delete >nul 2>&1')
        print(" Done.")
        
        # 2. 포트 8080 정리
        print("[-] Cleaning port 8080...", end="", flush=True)
        subprocess.run([
            'powershell', '-Command',
            '$procs = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | '
            'Select-Object -ExpandProperty OwningProcess -Unique; '
            'if ($procs) { $procs | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }'
        ], capture_output=True, text=True, timeout=5)
        print(" Done.")
        
        # 3. 락 파일 삭제
        print("[-] Removing lock files...", end="", flush=True)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for lock in ['main.lock', 'trading.lock']:
            path = os.path.join(script_dir, lock)
            if os.path.exists(path):
                try: 
                    os.remove(path)
                except: 
                    pass
        print(" Done.")
        
    except Exception as e:
        print(f" Error: {e}")
    
    print("\n✅ All processes stopped.")
    print("💡 You can close this window manually.")

if __name__ == "__main__":
    kill_everything()
    time.sleep(1)
