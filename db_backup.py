import shutil
import os
import datetime
from logger import logger

def backup_database():
    """데이터베이스(trading.db)를 backups 폴더에 날짜별로 백업합니다."""
    source_db = 'trading.db'
    backup_dir = 'backups'
    
    # 1. 원본 존재 확인
    if not os.path.exists(source_db):
        logger.error(f"❌ 백업 실패: {source_db} 파일이 존재하지 않습니다.")
        return False
        
    # 2. 백업 폴더 생성
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        logger.info(f"📁 백업 폴더 생성 완료: {backup_dir}")
        
    # 3. 백업 파일명 생성 (예: trading_2026-01-02_1734.db)
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M')
    backup_file = os.path.join(backup_dir, f'trading_{timestamp}.db')
    
    try:
        # 4. 파일 복사
        shutil.copy2(source_db, backup_file)
        
        # 5. 오래된 백업 정리 (최근 7일 혹은 10개만 유지하는 로직 추가 가능)
        all_backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith('trading_')])
        if len(all_backups) > 30: # 30개 넘으면 가장 오래된 것 삭제
            os.remove(all_backups[0])
            logger.info(f"🧹 오래된 백업 삭제: {all_backups[0]}")
            
        logger.info(f"✅ 데이터베이스 백업 완료: {backup_file}")
        return True
    except Exception as e:
        logger.error(f"❌ 백업 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    backup_database()
