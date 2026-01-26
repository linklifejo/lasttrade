from kiwoom_adapter import get_account_data
import json

def check_real_assets():
    print("=== [실전] 자산 현황 상세 조회 ===")
    try:
        # get_account_data()는 (holdings, summary) 튜플을 반환함
        holdings, summary = get_account_data()
        
        if not summary:
            print("❌ 계좌 요약 정보를 가져오지 못했습니다.")
            return

        # 주요 지표 추출 (RealKiwoomAPI.get_account_data 응답 기준)
        # dnca_tot_amt: 예수금
        # tot_evlu_amt: 총평가금액
        # tot_pchs_amt: 총매입금액
        # tdy_lspft_amt: 당일실현손익
        
        deposit = int(summary.get('dnca_tot_amt', summary.get('d2_entra', 0)))
        total_buy = int(summary.get('tot_pchs_amt', summary.get('tot_pur_amt', 0)))
        total_eval = int(summary.get('tot_evlu_amt', summary.get('prsm_dpst_aset_amt', 0)))
        realized_pl = int(summary.get('tdy_lspft_amt', summary.get('tot_pl', 0)))
        
        # 주식 평가액 (총평가금 - 예수금)
        stock_eval = total_eval - deposit
        # 평가 손익
        eval_pl = stock_eval - total_buy
        
        print(f"💰 총 자 산: {total_eval:,}원")
        print(f"💵 예 수 금: {deposit:,}원")
        print(f"📦 주식매입: {total_buy:,}원")
        print(f"📈 평가손익: {eval_pl:,}원")
        print(f"🏁 실현손익: {realized_pl:,}원")
        
        print("\n--- [실전] 보유 종목 리스트 ---")
        if not holdings:
            print("보유 종목 없음")
        else:
            for s in holdings:
                name = s.get('stk_nm', '알수없음')
                code = s.get('stk_cd', '').replace('A', '')
                qty = int(s.get('rmnd_qty', 0))
                avg_prc = float(s.get('avg_prc', 0))
                cur_prc = float(s.get('cur_prc', 0))
                pl_rt = s.get('pl_rt', '0.00')
                
                if qty > 0:
                    print(f"[{name}({code})] {qty}주 | 평균: {avg_prc:,.0f} | 현재: {cur_prc:,.0f} | 수익률: {pl_rt}%")

    except Exception as e:
        print(f"❌ 조회 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_real_assets()
