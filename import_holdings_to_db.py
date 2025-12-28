
import sys
import os
import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from kiwoom_adapter import get_my_stocks, get_current_api_mode
from database_trading_log import log_buy_to_db, get_db_connection
from logger import logger

def clean_val(val):
    """문자열의 앞뒤 공백 및 리딩 제로 제거 후 수치형 변환"""
    if val is None: return 0
    s = str(val).strip().lstrip('0')
    if not s or s == '': return 0
    try:
        return float(s)
    except:
        return 0

def import_holdings():
    """현재 보유 종목을 매매 보고서(DB)에 매수 기록으로 등록"""
    try:
        mode = get_current_api_mode().upper()
        logger.info(f"🚀 현재 모드({mode})의 보유 종목을 DB 매수 기록으로 동기화 시작...")

        # 1. 현재 보유 종목 조회
        stocks = get_my_stocks()
        if not stocks:
            logger.info("ℹ️ 현재 보유 중인 종목이 없습니다.")
            return

        # 2. DB 연결
        with get_db_connection() as conn:
            # 중복 방지를 위해 기존 매수 내역 삭제 (필요 시 선택)
            # conn.execute("DELETE FROM trades WHERE type='buy' AND mode=?", (mode,))
            # conn.commit()
            
            cursor = conn.execute("SELECT code FROM trades WHERE type='buy' AND mode=?", (mode,))
            existing_codes = {row['code'] for row in cursor.fetchall()}

        count = 0
        for s in stocks:
            code = s.get('stk_cd', '').replace('A', '')
            # 필드명 호환성 (pchs_avg_pric 또는 avg_prc)
            avg_price = clean_val(s.get('pchs_avg_pric', s.get('avg_prc', 0)))
            qty = int(clean_val(s.get('rmnd_qty', 0)))
            name = s.get('stk_nm', code)
            
            if qty <= 0: continue

            # 가격이 0원인 기존 내역이 있다면 삭제 후 새로 등록 (정규화)
            if code in existing_codes:
                with get_db_connection() as conn:
                    p_row = conn.execute("SELECT price FROM trades WHERE code=? AND type='buy' AND mode=?", (code, mode)).fetchone()
                    if p_row and float(p_row['price']) <= 0:
                        conn.execute("DELETE FROM trades WHERE code=? AND type='buy' AND mode=?", (code, mode))
                        conn.commit()
                        existing_codes.remove(code)

            if code not in existing_codes:
                log_buy_to_db(code, name, qty, avg_price, mode=mode)
                logger.info(f"✅ 동기화됨: {name}({code}) {qty}주 @ {avg_price:,.0f}원")
                count += 1
            else:
                logger.info(f"ℹ️ 스킵(이미 존재): {name}({code})")

        logger.info(f"✨ 총 {count}개의 종목이 {mode} 모드 매매 보고서에 동기화되었습니다.")

    except Exception as e:
        logger.error(f"❌ 보유 종목 동기화 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import_holdings()
