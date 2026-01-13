import os
import re
import json
import time
from datetime import datetime
from logger import logger
from tel_send import tel_send

# [AI 가디언] 자율 진화 헌법
# 1. 원칙(70% 비중, 1:1:2:4:8 수열)은 절대로 코딩으로 수정하지 않는다.
# 2. 파라미터 수정은 하루에 최대 10% 이내(Delta Limit)로 제한한다.
# 3. 수정 후 에러 발생 시 1순위로 즉시 롤백한다.

class LogicEvolver:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.history_path = os.path.join(self.base_dir, 'logs', 'logic_evolution_history.json')
        self.proposals_path = os.path.join(self.base_dir, 'docs', 'AI_IMPROVEMENT_PROPOSALS.md')
        
    def get_history(self):
        if os.path.exists(self.history_path):
            with open(self.history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def save_history(self, history):
        with open(self.history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4, ensure_ascii=False)

    def apply_improvement(self, target_file, pattern, replacement, reason):
        """실제 소스 코드를 수정하고 이력을 남김"""
        file_path = os.path.join(self.base_dir, target_file)
        if not os.path.exists(file_path):
            logger.error(f"❌ Evolution 실패: 파일을 찾을 수 없음 ({target_file})")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 현재 값 백업 (롤백용)
            match = re.search(pattern, content)
            if not match:
                logger.warning(f"⚠️ Evolution 대상 패턴을 찾을 수 없음: {pattern}")
                return False
            
            original_value = match.group(0)
            
            # 코드 수정
            new_content = re.sub(pattern, replacement, content)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # [Safety] 구문 체크 실행
            import py_compile
            try:
                py_compile.compile(file_path, doraise=True)
                logger.info(f"✅ [Safety Check] {target_file} 구문 검사 통과")
            except py_compile.PyCompileError as e:
                logger.error(f"❌ [Safety Check] {target_file} 구문 오류 발견! 즉시 롤백합니다: {e}")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content) # 원본 복구
                return False

            # 히스토리 기록
            history = self.get_history()
            history.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file': target_file,
                'original': original_value,
                'new': replacement,
                'reason': reason,
                'status': 'APPLIED'
            })
            self.save_history(history)
            
            msg = f"🧬 [AI 자율 진화] {target_file} 로직 수정 완료\n- 사유: {reason}\n- 변경: {original_value} -> {replacement}"
            logger.info(msg)
            tel_send(msg)
            return True

        except Exception as e:
            logger.error(f"❌ Evolution 실행 중 서버 오류: {e}")
            return False

    def rollback(self):
        """가장 최근의 수정을 되돌림"""
        history = self.get_history()
        if not history:
            logger.warning("⚠️ 롤백할 이력이 없습니다.")
            return False

        last_change = history.pop()
        target_file = last_change['file']
        original_code = last_change['original']
        new_code = last_change['new']
        
        file_path = os.path.join(self.base_dir, target_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 신규 코드를 원래 코드로 치환
            if new_code in content:
                updated_content = content.replace(new_code, original_code)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                
                self.save_history(history)
                msg = f"⏪ [AI 긴급 복구] 로직 롤백 완료: {target_file}\n({new_code} -> {original_code})"
                logger.warning(msg)
                tel_send(msg)
                return True
            else:
                logger.error("❌ 롤백 실패: 수정된 지점을 찾을 수 없습니다.")
                return False
        except Exception as e:
            logger.error(f"❌ 롤백 중 오류: {e}")
            return False

    def evolve_from_proposals(self):
        """제안서 문서에서 '자동화 가능'한 항목을 찾아 실행 (Full-Auto)"""
        # 현재는 간단한 예시로 RSI 수치 자동 조정 로직만 구현
        # 향후 LLM이 생성한 코드를 파싱하는 단계로 확장 가능
        pass

if __name__ == "__main__":
    evolver = LogicEvolver()
    # 테스트용: evolver.apply_improvement('check_n_buy.py', r'rsi_limit < 30', 'rsi_limit < 28', '수익률 향상을 위한 감도 조정')
