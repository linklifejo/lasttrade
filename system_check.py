#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
시스템 전체 상태 점검 스크립트
"""
import os
import sys
import sqlite3
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def check_system():
    print("=" * 80)
    print(f"🔍 ANTIGRAVITY 트레이딩 시스템 전체 점검")
    print(f"점검 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 1. 데이터베이스 설정 확인
    print("\n📊 [1] 데이터베이스 설정 (Settings)")
    print("-" * 80)
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT key, value FROM settings 
            WHERE key IN (
                'use_mock_server', 'is_paper_trading', 'process_name',
                'target_stock_count', 'split_buy_cnt', 'take_profit_rate',
                'stop_loss_rate', 'time_cut_minutes', 'liquidation_time'
            )
            ORDER BY key
        """)
        
        settings = {}
        for row in cursor.fetchall():
            settings[row['key']] = row['value']
            print(f"  {row['key']:30s} = {row['value']}")
        
        # 모드 판별
        use_mock = settings.get('use_mock_server', 'true') == 'true'
        is_paper = settings.get('is_paper_trading', 'true') == 'true'
        
        if use_mock:
            mode_str = "🎮 내부 Mock 서버 (테스트)"
        elif is_paper:
            mode_str = "📝 키움 모의투자 서버"
        else:
            mode_str = "💰 키움 실전투자 서버 (LIVE)"
        
        print(f"\n  현재 운영 모드: {mode_str}")
        
    except Exception as e:
        print(f"  ❌ 설정 조회 실패: {e}")
    
    # 2. Mock 계좌 상태 (Mock 모드인 경우)
    if use_mock:
        print("\n💰 [2] Mock 계좌 상태")
        print("-" * 80)
        try:
            cursor = conn.execute("SELECT cash, total_eval FROM mock_account WHERE id=1")
            row = cursor.fetchone()
            if row:
                print(f"  현금 잔고: {row['cash']:,}원")
                print(f"  총 평가액: {row['total_eval']:,}원")
            
            cursor = conn.execute("""
                SELECT COUNT(*) as cnt, SUM(qty) as total_qty 
                FROM mock_holdings WHERE qty > 0
            """)
            row = cursor.fetchone()
            if row:
                print(f"  보유 종목 수: {row['cnt']}개")
                print(f"  총 보유 수량: {row['total_qty'] or 0}주")
        except Exception as e:
            print(f"  ❌ Mock 계좌 조회 실패: {e}")
    
    # 3. 거래 내역 통계
    print("\n📈 [3] 거래 내역 통계 (Trades)")
    print("-" * 80)
    try:
        # 모드별 거래 건수
        cursor = conn.execute("""
            SELECT mode, type, COUNT(*) as cnt 
            FROM trades 
            GROUP BY mode, type 
            ORDER BY mode, type
        """)
        print("  모드별 거래 건수:")
        for row in cursor.fetchall():
            print(f"    [{row['mode']:5s}] {row['type']:4s}: {row['cnt']:4d}건")
        
        # 오늘 거래 내역
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = conn.execute("""
            SELECT mode, type, COUNT(*) as cnt 
            FROM trades 
            WHERE timestamp LIKE ?
            GROUP BY mode, type
        """, (f'{today}%',))
        
        print(f"\n  오늘({today}) 거래:")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"    [{row['mode']:5s}] {row['type']:4s}: {row['cnt']:4d}건")
        else:
            print("    거래 없음")
            
    except Exception as e:
        print(f"  ❌ 거래 통계 조회 실패: {e}")
    
    # 4. 보유 시간 추적 (Held Times)
    print("\n⏱️  [4] 보유 시간 추적 (Held Times)")
    print("-" * 80)
    try:
        cursor = conn.execute("""
            SELECT code, held_since, updated_at 
            FROM held_times 
            ORDER BY held_since DESC 
            LIMIT 10
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"  최근 보유 종목 (최대 10개):")
            for row in rows:
                held_dt = datetime.fromtimestamp(row['held_since'])
                duration = datetime.now() - held_dt
                minutes = int(duration.total_seconds() / 60)
                print(f"    {row['code']:6s} - 보유시간: {minutes:4d}분 (시작: {held_dt.strftime('%H:%M:%S')})")
        else:
            print("  현재 보유 시간 추적 중인 종목 없음")
    except Exception as e:
        print(f"  ❌ 보유 시간 조회 실패: {e}")
    
    # 5. 시스템 상태 (최근 업데이트)
    print("\n🤖 [5] 시스템 상태 (System Status)")
    print("-" * 80)
    try:
        cursor = conn.execute("SELECT status_json, updated_at FROM system_status WHERE id=1")
        row = cursor.fetchone()
        if row:
            import json
            status = json.loads(row['status_json'])
            summary = status.get('summary', {})
            print(f"  마지막 업데이트: {row['updated_at']}")
            print(f"  봇 가동 상태: {'🟢 실행 중' if summary.get('bot_running') else '🔴 정지'}")
            print(f"  API 모드: {summary.get('api_mode', 'N/A')}")
            print(f"  총 자산: {summary.get('total_asset', 0):,}원")
            print(f"  보유 종목 수: {len(status.get('holdings', []))}개")
        else:
            print("  시스템 상태 정보 없음 (봇이 아직 실행되지 않았거나 초기화 중)")
    except Exception as e:
        print(f"  ❌ 시스템 상태 조회 실패: {e}")
    
    # 6. 웹 명령 큐
    print("\n📬 [6] 웹 명령 큐 (Web Commands)")
    print("-" * 80)
    try:
        cursor = conn.execute("""
            SELECT command, status, created_at 
            FROM web_commands 
            WHERE status = 'pending'
            ORDER BY id DESC 
            LIMIT 5
        """)
        rows = cursor.fetchall()
        if rows:
            print("  대기 중인 명령:")
            for row in rows:
                print(f"    {row['command']:10s} - {row['created_at']}")
        else:
            print("  대기 중인 명령 없음")
    except Exception as e:
        print(f"  ❌ 명령 큐 조회 실패: {e}")
    
    conn.close()
    
    # 7. 로그 파일 상태
    print("\n📝 [7] 로그 파일 상태")
    print("-" * 80)
    try:
        today_str = datetime.now().strftime('%Y%m%d')
        log_files = [
            f'logs/trading_{today_str}.log',
            f'logs/error_{today_str}.log'
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                size = os.path.getsize(log_file)
                size_mb = size / (1024 * 1024)
                print(f"  {log_file:30s}: {size_mb:6.2f} MB")
            else:
                print(f"  {log_file:30s}: 파일 없음")
    except Exception as e:
        print(f"  ❌ 로그 파일 확인 실패: {e}")
    
    # 8. 프로세스 상태
    print("\n⚙️  [8] 프로세스 상태")
    print("-" * 80)
    try:
        # 간단한 프로세스 확인 (Windows)
        import subprocess
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Process python | Select-Object Id, ProcessName, StartTime | Format-Table -AutoSize'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("  실행 중인 Python 프로세스:")
            for line in result.stdout.strip().split('\n')[:10]:  # 최대 10개만
                print(f"    {line}")
        else:
            print("  프로세스 조회 실패")
    except Exception as e:
        print(f"  ❌ 프로세스 확인 실패: {e}")
    
    print("\n" + "=" * 80)
    print("✅ 시스템 점검 완료")
    print("=" * 80)

if __name__ == "__main__":
    check_system()
