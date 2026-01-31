from analyze_tools import get_technical_indicators
from logger import logger

class TechnicalJudge:
    """키움 검색식에서 올라온 종목의 '성향'을 분석하여 최종 판단을 내리는 보조 판독기"""
    
    @staticmethod
    def get_weight(key, default):
        """DB에서 학습된 가중치 로드"""
        try:
            from database import get_db_connection
            with get_db_connection() as conn:
                res = conn.execute("SELECT value FROM learned_weights WHERE key = ?", (key,)).fetchone()
                return res[0] if res else default
        except:
            return default

    @staticmethod
    def judge_buy(code):
        """매수 적합성 판독 (설정창 팩터 연동 버전)"""
        from get_setting import get_setting
        
        indicators = get_technical_indicators(code, '1m')
        if not indicators:
            return True, "데이터 부족으로 기본 통과" # 데이터가 아직 안 쌓였으면 일단 통과
            
        score = 0
        reasons = []
        
        # 설정 로드
        overbought_disp = float(get_setting('tj_overbought_disparity', 105.0))
        oversold_disp = float(get_setting('tj_oversold_disparity', 98.0))
        
        # 2. 이격도 체크 (단기 과열 여부)
        disp5 = indicators['disparity_5']
        if disp5 > overbought_disp: # MA5보다 너무 높으면 추격 매수 위험
            score -= int(get_setting('tj_score_overbought', 20))
            reasons.append(f"단기 과열(MA5 이격 {disp5:.1f}%)")
        elif disp5 < oversold_disp: # 눌림목 가능성
            score += int(get_setting('tj_score_oversold', 15))
            reasons.append(f"눌림목 구간(MA5 이격 {disp5:.1f}%)")
            
        # 3. 추세 체크
        if indicators['trend'] == "UP":
            score += int(get_setting('tj_score_trend_up', 15))
            reasons.append("정배열 추세")
        else:
            score -= int(get_setting('tj_score_trend_down', 10))
            reasons.append("역배열/하락 추세")
            
        # 최종 결정 (시간 적응형 문턱 적용)
        import datetime
        from kiwoom_adapter import get_current_api_mode
        
        now = datetime.datetime.now()
        current_mode = get_current_api_mode()
        
        base_threshold = int(get_setting('tj_threshold_base', 20))
        afternoon_threshold = int(get_setting('tj_threshold_afternoon', 40))
        afternoon_hour = int(get_setting('tj_afternoon_hour', 14))
        
        threshold = base_threshold
        
        # [Time-Adaptive] 키움 실전(Real) 모드에서만 오후 특정 시간 이후 문턱을 상향
        if current_mode == "Real" and now.hour >= afternoon_hour:
            threshold = afternoon_threshold
            logger.info(f"⏰ [Time-Adaptive] {afternoon_hour}시 이후 필터 강화 적용 ({threshold}점)")

        passed = score >= threshold
        
        status_msg = f"점수: {score} (기준: {threshold}) | 사유: {', '.join(reasons)}"
        logger.info(f"⚖️ [Technical Judge] {code} 판독 결과 -> {'✅ 승인' if passed else '❌ 거절'} ({status_msg})")
        
        return passed, status_msg

technical_judge = TechnicalJudge()
