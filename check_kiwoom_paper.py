from database_helpers import get_setting, save_setting
import config
from kiwoom_adapter import get_account_data, reset_api

def check_kiwoom_paper_assets():
    print("=== [키움 모의투자] 자산 현황 조회 ===")
    
    # 현재 설정 백업
    original_mock = get_setting('use_mock_server')
    original_paper = get_setting('is_paper_trading')
    
    try:
        # 강제로 '키움 API' + '모의투자' 모드로 설정 (메모리상)
        # config 객체는 DB 값을 실시간으로 읽으므로, DB 값을 잠시 변경하거나 
        # 혹은 config._cfg의 설정을 패치해야 할 수도 있지만, 
        # config.py는 get_setting을 호출하므로 DB를 잠깐 바꿉니다.
        
        save_setting('use_mock_server', False)
        save_setting('is_paper_trading', True)
        
        # API 인스턴스 초기화 필요 (config 값이 바뀌었으므로)
        reset_api()
        
        holdings, summary = get_account_data()
        
        if not summary:
            print("❌ 키움 모의투자 서버에서 데이터를 가져오지 못했습니다. (접속 정보 확인 필요)")
            return

        deposit = int(summary.get('dnca_tot_amt', summary.get('d2_entra', 0)))
        total_buy = int(summary.get('tot_pchs_amt', summary.get('tot_pur_amt', 0)))
        total_eval = int(summary.get('tot_evlu_amt', summary.get('prsm_dpst_aset_amt', 0)))
        realized_pl = int(summary.get('tdy_lspft_amt', summary.get('tot_pl', 0)))
        
        stock_eval = total_eval - deposit
        eval_pl = stock_eval - total_buy
        
        print(f"💰 총 자 산: {total_eval:,}원")
        print(f"💵 예 수 금: {deposit:,}원")
        print(f"📦 주식매입: {total_buy:,}원")
        print(f"📈 평가손익: {eval_pl:,}원")
        print(f"🏁 실현손익: {realized_pl:,}원")
        
        print("\n--- [모의] 보유 종목 리스트 ---")
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
    finally:
        # 설정 원복
        save_setting('use_mock_server', original_mock)
        save_setting('is_paper_trading', original_paper)
        reset_api()

if __name__ == "__main__":
    check_kiwoom_paper_assets()
