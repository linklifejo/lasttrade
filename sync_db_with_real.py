
import asyncio
import sqlite3
import datetime
from kiwoom_adapter import fn_kt00004, fn_au10001
from database_helpers import get_db_connection

async def sync_db():
    print("🚀 [DB 동기화] 실제 잔고와 DB 상태 일치 작업 시작")
    
    # 1. API 잔고 조회
    token = fn_au10001()
    if not token:
        print("❌ 토큰 실패")
        return

    real_holdings = fn_kt00004(token=token)
    real_codes = set()
    print(f"📊 실제 API 잔고: {len(real_holdings)}개 종목")
    
    for stock in real_holdings:
        code = stock['stk_cd'].replace('A', '')
        real_codes.add(code)
        print(f"   - 보유: {stock['stk_nm']} ({code}) {int(stock['rmnd_qty'])}주")

    # 2. DB 상태 조회 (오늘 매수 - 매도 > 0 인 것들)
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 각 종목별 순매수량 계산
    rows = cursor.execute("SELECT code, type, qty FROM trades WHERE timestamp LIKE ?", (f"{today_str}%",)).fetchall()
    
    db_calc = {}
    for r in rows:
        c, t, q = r['code'], r['type'], r['qty']
        if c not in db_calc: db_calc[c] = 0
        if t == 'buy': db_calc[c] += q
        elif t == 'sell': db_calc[c] -= q
        
    print(f"📚 DB상 추정 보유 종목:")
    ghosts = []
    
    for code, qty in db_calc.items():
        if qty > 0:
            print(f"   - DB 기록: {code} 잔량 {qty}")
            if code not in real_codes:
                print(f"     👉 [유령 감지] 실제론 없음! -> 강제 청산 처리 필요")
                ghosts.append((code, qty))
    
    # 3. 유령 종목 강제 매도 처리 (DB에만 sell 로그 추가)
    if ghosts:
        print(f"👻 유령 종목 {len(ghosts)}개 발견. DB 정리 시작...")
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for code, qty in ghosts:
            # 매도 로그 삽입 (최소 컬럼만 사용)
            try:
                # Mode 컬럼이 있는지 확인
                cursor.execute("SELECT mode FROM trades LIMIT 1")
                has_mode = True
            except:
                has_mode = False

            if has_mode:
                cursor.execute(
                    "INSERT INTO trades (timestamp, code, name, type, price, qty, mode) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (now, code, 'GHOST_FIX', 'sell', 0, qty, 'REAL')
                )
            else:
                cursor.execute(
                    "INSERT INTO trades (timestamp, code, name, type, price, qty) VALUES (?, ?, ?, ?, ?, ?)",
                    (now, code, 'GHOST_FIX', 'sell', 0, qty)
                )

            print(f"   ✅ {code}: {qty}주 'sell' 로그 강제 주입 완료")
        
        conn.commit()
        print("✨ DB 동기화 완료. 이제 봇이 0개로 인식하고 매수를 재개할 것입니다.")
    else:
        print("✨ DB와 실제 잔고가 일치합니다. (유령 없음)")
        
    conn.close()

if __name__ == "__main__":
    asyncio.run(sync_db())
