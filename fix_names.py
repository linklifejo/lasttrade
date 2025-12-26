import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

# 종목 코드 -> 이름 매핑
STOCK_NAMES = {
    '009150': '삼성전기',
    '000810': '삼성화재',
    '352820': '하이브',
    '009540': 'HD현대중공업',
    '000720': '현대건설',
    '035720': '카카오',
    '105560': 'KB금융',
    '035420': 'NAVER',
    '055550': '신한지주',
}

def fix_stock_names():
    """Test_ 이름을 실제 종목명으로 수정"""
    conn = sqlite3.connect(DB_FILE)
    
    try:
        for code, name in STOCK_NAMES.items():
            conn.execute('''
                UPDATE mock_stocks 
                SET name = ? 
                WHERE code = ?
            ''', (name, code))
            print(f"✅ {code}: Test_{code} → {name}")
        
        conn.commit()
        print(f"\n총 {len(STOCK_NAMES)}개 종목명 수정 완료!")
        
    except Exception as e:
        print(f"❌ 오류: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_stock_names()
