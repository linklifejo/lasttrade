"""
DB 마이그레이션: trading_mode 필드 추가
- trading_mode 필드를 settings 테이블에 추가
- 기존 use_mock_server와 is_paper_trading 값에서 trading_mode 값 계산
"""
import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

def migrate_trading_mode():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 기존 설정 읽기
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('use_mock_server', 'is_paper_trading')")
        settings = {row['key']: row['value'] for row in cursor.fetchall()}
        
        use_mock = settings.get('use_mock_server', 'true').lower() == 'true'
        is_paper = settings.get('is_paper_trading', 'false').lower() == 'true'
        
        # trading_mode 계산 (1=Mock, 2=Paper, 3=Real)
        if use_mock:
            trading_mode = 1
        elif is_paper:
            trading_mode = 2
        else:
            trading_mode = 3
        
        # trading_mode 저장
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES ('trading_mode', ?, datetime('now'))
        """, (str(trading_mode),))
        
        conn.commit()
        print(f"✅ trading_mode 마이그레이션 완료: {trading_mode}")
        print(f"   - use_mock_server: {use_mock}")
        print(f"   - is_paper_trading: {is_paper}")
        print(f"   - trading_mode: {trading_mode} ({'Mock' if trading_mode == 1 else 'Paper' if trading_mode == 2 else 'Real'})")
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_trading_mode()
