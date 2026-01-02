"""
일일 데이터 정리 스크립트
- 다음날 장 시작 전(09:00) 실행
- 전일 데이터 삭제 (당일 데이터만 유지)
- AI 학습 데이터는 영구 보관
"""
import sqlite3
import os
from datetime import datetime, timedelta
from logger import logger

from db_backup import backup_database
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def cleanup_daily_data():
    """전일 데이터 정리 시작 전 백업을 먼저 수행합니다."""
    logger.info("💾 데이터 정리 전 자동 백업을 시작합니다.")
    backup_database()
    
    """전일 데이터 삭제 (당일만 유지)"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 오늘 날짜 (YYYY-MM-DD 형식)
        today = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"🧹 일일 데이터 정리 시작 (기준일: {today})")
        
        # 1. 전일 거래 내역 삭제 (당일만 유지)
        cursor.execute("DELETE FROM trades WHERE DATE(timestamp) < ?", (today,))
        deleted_trades = cursor.rowcount
        logger.info(f"  ✓ trades: {deleted_trades:,}개 삭제")
        
        # 2. 전일 분봉 데이터 삭제
        cursor.execute("DELETE FROM candle_history WHERE DATE(timestamp) < ?", (today,))
        deleted_candles = cursor.rowcount
        logger.info(f"  ✓ candle_history: {deleted_candles:,}개 삭제")
        
        # 3. 전일 시그널 스냅샷 삭제
        cursor.execute("DELETE FROM signal_snapshots WHERE DATE(timestamp) < ?", (today,))
        deleted_signals = cursor.rowcount
        logger.info(f"  ✓ signal_snapshots: {deleted_signals:,}개 삭제")
        
        # 4. 전일 대응 메트릭 삭제 (고아 레코드 방지)
        cursor.execute("""
            DELETE FROM response_metrics 
            WHERE signal_id NOT IN (SELECT id FROM signal_snapshots)
        """)
        deleted_metrics = cursor.rowcount
        logger.info(f"  ✓ response_metrics: {deleted_metrics:,}개 삭제")
        
        # 5. 전일 자산 히스토리 삭제
        cursor.execute("DELETE FROM asset_history WHERE DATE(timestamp) < ?", (today,))
        deleted_assets = cursor.rowcount
        logger.info(f"  ✓ asset_history: {deleted_assets:,}개 삭제")
        
        # 6. 전일 가격 히스토리 삭제 (테이블이 있는 경우)
        try:
            cursor.execute("DELETE FROM price_history WHERE DATE(timestamp) < ?", (today,))
            deleted_prices = cursor.rowcount
            logger.info(f"  ✓ price_history: {deleted_prices:,}개 삭제")
        except sqlite3.OperationalError:
            pass  # 테이블이 없으면 스킵
        
        # 7. 웹 명령 히스토리 정리 (완료된 명령만)
        cursor.execute("""
            DELETE FROM web_commands 
            WHERE status = 'completed' AND DATE(timestamp) < ?
        """, (today,))
        deleted_commands = cursor.rowcount
        logger.info(f"  ✓ web_commands: {deleted_commands:,}개 삭제")
        
        conn.commit()
        
        # 8. VACUUM (공간 회수)
        logger.info("  🔧 DB VACUUM 실행 중...")
        cursor.execute("VACUUM")
        logger.info("  ✓ VACUUM 완료")
        
        # 9. DB 크기 확인
        db_size = os.path.getsize(DB_FILE) / (1024 * 1024 * 1024)  # GB
        logger.info(f"  📊 현재 DB 크기: {db_size:.2f} GB")
        
        conn.close()
        
        total_deleted = (deleted_trades + deleted_candles + deleted_signals + 
                        deleted_metrics + deleted_assets)
        logger.info(f"✅ 정리 완료: 총 {total_deleted:,}개 레코드 삭제")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 데이터 정리 실패: {e}")
        return False

def check_preserved_data():
    """AI 학습 데이터가 보존되었는지 확인"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 보존되어야 할 테이블 확인
        preserved_tables = {
            'learned_weights': 'AI 학습 가중치',
            'sim_performance': '시뮬레이션 성적',
            'sim_configs': '시뮬레이션 설정',
            'sim_scenarios': '시나리오',
            'settings': '시스템 설정'
        }
        
        logger.info("📚 AI 학습 데이터 보존 확인:")
        for table, desc in preserved_tables.items():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                logger.info(f"  ✓ {desc} ({table}): {count:,}개")
            except sqlite3.OperationalError:
                logger.warning(f"  ⚠ {table} 테이블 없음")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ 보존 데이터 확인 실패: {e}")

if __name__ == "__main__":
    logger.info("="*50)
    logger.info("일일 데이터 정리 시작")
    logger.info("="*50)
    
    # 정리 실행
    success = cleanup_daily_data()
    
    if success:
        # 보존 데이터 확인
        check_preserved_data()
        logger.info("="*50)
        logger.info("✅ 모든 작업 완료")
        logger.info("="*50)
    else:
        logger.error("❌ 정리 작업 실패")
