"""
좀비 프로세스 완전 제거 스크립트
모든 트레이딩 봇 관련 프로세스를 강제 종료합니다.
"""
import os
import subprocess
import time

def kill_all_zombies():
    """모든 좀비 프로세스를 강제 종료"""
    print("=" * 60)
    print("🧟 ZOMBIE KILLER - 좀비 프로세스 완전 제거")
    print("=" * 60)
    
    # 1. WMIC로 프로세스 종료
    print("\n[1/4] Killing processes via WMIC...")
    scripts = ['bot.py', 'web_server.py', 'watchdog.py', 'start.py']
    for script in scripts:
        print(f"  - Killing {script}...", end="", flush=True)
        result = os.system(f'wmic process where "commandline like \'%%{script}%%\'" delete >nul 2>&1')
        print(" ✓")
    
    time.sleep(1)
    
    # 2. PowerShell로 포트 점유 프로세스 종료
    print("\n[2/4] Cleaning port 8080...")
    try:
        subprocess.run([
            'powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
            '''
            $ErrorActionPreference = "SilentlyContinue"
            $procs = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | 
                     Select-Object -ExpandProperty OwningProcess -Unique
            if ($procs) {
                $procs | ForEach-Object {
                    $proc = Get-Process -Id $_ -ErrorAction SilentlyContinue
                    if ($proc) {
                        Write-Host "  - Killing PID $_ ($($proc.ProcessName))"
                        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
                    }
                }
            } else {
                Write-Host "  - Port 8080 is clean"
            }
            '''
        ], timeout=10)
    except Exception as e:
        print(f"  ⚠️ Warning: {e}")
    
    # 3. 고아 Python 프로세스 검색 및 종료
    print("\n[3/4] Searching for orphaned Python processes...")
    try:
        result = subprocess.run([
            'powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
            '''
            $ErrorActionPreference = "SilentlyContinue"
            $procs = Get-WmiObject Win32_Process | Where-Object {
                $_.CommandLine -match "bot\\.py|web_server\\.py|watchdog\\.py|start\\.py"
            }
            if ($procs) {
                $procs | ForEach-Object {
                    Write-Host "  - Found PID $($_.ProcessId): $($_.CommandLine)"
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                }
            } else {
                Write-Host "  - No orphaned processes found"
            }
            '''
        ], timeout=10)
    except Exception as e:
        print(f"  ⚠️ Warning: {e}")
    
    # 4. 락 파일 정리
    print("\n[4/4] Removing lock files...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lock_files = ['main.lock', 'web.lock', 'bot.lock', 'trading.lock']
    for lock in lock_files:
        path = os.path.join(script_dir, lock)
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"  - Removed {lock}")
            except Exception as e:
                print(f"  ⚠️ Failed to remove {lock}: {e}")
    
    # 5. 최종 확인
    print("\n" + "=" * 60)
    print("🎯 Verifying cleanup...")
    try:
        result = subprocess.run([
            'powershell', '-NoProfile', '-Command',
            '''
            $procs = Get-WmiObject Win32_Process | Where-Object {
                $_.CommandLine -match "bot\\.py|web_server\\.py|watchdog\\.py|start\\.py"
            }
            if ($procs) {
                Write-Host "⚠️ WARNING: Still found running processes:"
                $procs | ForEach-Object {
                    Write-Host "  - PID $($_.ProcessId): $($_.CommandLine)"
                }
            } else {
                Write-Host "✅ All processes successfully terminated!"
            }
            '''
        ], timeout=5)
    except:
        pass
    
    print("=" * 60)
    print("\n✅ Zombie cleanup completed!")
    print("💡 You can now safely restart the system.\n")

if __name__ == "__main__":
    try:
        kill_all_zombies()
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        input("\nPress Enter to close...")
