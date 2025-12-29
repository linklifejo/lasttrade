"""
웹 대시보드 Stop 명령 시뮬레이션 테스트
DB에 stop 명령을 직접 삽입하여 봇이 종료되는지 확인
"""
import sqlite3
import time

def send_web_stop_command():
    """웹 대시보드에서 stop 버튼을 누른 것처럼 DB에 명령 삽입"""
    print("=" * 60)
    print("🧪 웹 대시보드 Stop 명령 시뮬레이션 테스트")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # 1. 기존 pending 명령 확인
        cursor.execute("SELECT * FROM web_commands WHERE status = 'pending'")
        pending = cursor.fetchall()
        if pending:
            print(f"\n⚠️ 기존 pending 명령 {len(pending)}개 발견:")
            for cmd in pending:
                print(f"  - ID: {cmd[0]}, Command: {cmd[1]}, Created: {cmd[3]}")
        
        # 2. stop 명령 삽입
        print("\n📝 DB에 'stop' 명령 삽입 중...")
        cursor.execute("""
            INSERT INTO web_commands (command, status, created_at)
            VALUES ('stop', 'pending', datetime('now', 'localtime'))
        """)
        conn.commit()
        cmd_id = cursor.lastrowid
        print(f"✅ 명령 삽입 완료 (ID: {cmd_id})")
        
        # 3. 봇이 명령을 처리할 때까지 대기
        print("\n⏳ 봇이 명령을 처리할 때까지 대기 중...")
        max_wait = 30  # 최대 30초 대기
        for i in range(max_wait):
            time.sleep(1)
            cursor.execute("SELECT status FROM web_commands WHERE id = ?", (cmd_id,))
            result = cursor.fetchone()
            if result and result[0] == 'completed':
                print(f"\n✅ 명령 처리 완료! ({i+1}초 소요)")
                break
            print(f"  대기 중... {i+1}/{max_wait}초", end='\r')
        else:
            print(f"\n⚠️ {max_wait}초 동안 명령이 처리되지 않았습니다.")
            print("   봇이 실행 중인지 확인하세요.")
        
        # 4. 최종 상태 확인
        print("\n📊 최종 상태:")
        cursor.execute("SELECT * FROM web_commands WHERE id = ?", (cmd_id,))
        final = cursor.fetchone()
        if final:
            print(f"  - ID: {final[0]}")
            print(f"  - Command: {final[1]}")
            print(f"  - Status: {final[2]}")
            print(f"  - Created: {final[3]}")
            print(f"  - Completed: {final[4]}")
        
        conn.close()
        
        # 5. 프로세스 확인
        print("\n🔍 봇 프로세스 확인:")
        import subprocess
        result = subprocess.run([
            'powershell', '-Command',
            'Get-Process python -ErrorAction SilentlyContinue | '
            'Where-Object { $_.CommandLine -match "bot\\.py" } | '
            'Select-Object Id, ProcessName'
        ], capture_output=True, text=True, timeout=5)
        
        if result.stdout.strip():
            print("  ⚠️ bot.py 프로세스가 아직 실행 중입니다:")
            print(result.stdout)
            print("\n  💡 stop 명령이 처리되었지만 프로세스가 종료되지 않았습니다.")
            print("     로그를 확인하여 문제를 파악하세요.")
        else:
            print("  ✅ bot.py 프로세스가 종료되었습니다!")
            print("\n🎉 테스트 성공! stop 명령이 정상적으로 작동합니다.")
        
    except sqlite3.Error as e:
        print(f"\n❌ DB 오류: {e}")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    send_web_stop_command()
