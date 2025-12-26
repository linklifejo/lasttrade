import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')

# 전체 종목 매핑 (rt_search.py와 동일)
STOCK_NAMES = {
    '005930': '삼성전자', '000660': 'SK하이닉스', '035420': 'NAVER', '051910': 'LG화학', 
    '068270': '셀트리온', '006400': '삼성SDI', '005490': 'POSCO홀딩스',
    '035720': '카카오', '105560': 'KB금융', '055550': '신한지주', 
    '000270': '기아', '005380': '현대차', '012330': '현대모비스', '028260': '삼성물산',
    '096770': 'SK이노베이션', '009540': 'HD현대중공업', '003550': 'LG', 
    '066570': 'LG전자', '018260': '삼성에스디에스', '352820': '하이브',
    '015760': '한국전력', '034020': '두산에너빌리티', '010140': '삼성중공업', 
    '000720': '현대건설', '011200': 'HMM', '003490': '대한항공', '009830': '한화솔루션',
    '017670': 'SK텔레콤', '011170': '롯데케미칼', '010950': 'S-Oil', 
    '086790': '하나금융지주', '009150': '삼성전기', '032830': '삼성생명', 
    '000810': '삼성화재', '259960': '크래프톤'
}

def fix_all_test_names():
    """모든 Test_ 이름을 실제 종목명으로 수정"""
    conn = sqlite3.connect(DB_FILE)
    
    try:
        # 1. Test_로 시작하는 모든 종목 찾기
        cursor = conn.execute("SELECT code, name FROM mock_stocks WHERE name LIKE 'Test_%'")
        test_stocks = cursor.fetchall()
        
        print(f"발견된 Test_ 종목: {len(test_stocks)}개\n")
        
        fixed_count = 0
        for code, old_name in test_stocks:
            if code in STOCK_NAMES:
                new_name = STOCK_NAMES[code]
                conn.execute('UPDATE mock_stocks SET name = ? WHERE code = ?', (new_name, code))
                print(f"✅ {code}: {old_name} → {new_name}")
                fixed_count += 1
            else:
                print(f"⚠️  {code}: 매핑 정보 없음 ({old_name})")
        
        conn.commit()
        print(f"\n총 {fixed_count}개 종목명 수정 완료!")
        
    except Exception as e:
        print(f"❌ 오류: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_all_test_names()
