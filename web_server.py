"""
웹 대시보드 서버 (FastAPI)
- 브라우저에서 실시간으로 자산 현황/보유 종목/매도 내역을 확인
- 설정 변경 지원
"""
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from logger import logger

# 프로젝트 디렉토리
BASE_DIR = Path(__file__).parent
STATUSLOG_FILE = os.path.join(BASE_DIR, "logs/trading_{}.log".format(datetime.now().strftime("%Y%m%d")))
SELL_LOG_FILE = Path(os.path.join(BASE_DIR, "sell_log.json"))
TRADING_LOG_FILE = Path(os.path.join(BASE_DIR, "trading_log.json"))
SETTINGS_FILE = BASE_DIR / "settings.json"
STATUS_FILE = BASE_DIR / "status.json"
COMMAND_FILE = os.path.join(BASE_DIR, "web_command.json")

app = FastAPI(title="Kiwoom Trading Bot Dashboard")

# Static 파일 서빙 (CSS, JS)
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
# app.mount 대신 아래의 커스텀 핸들러 사용 (캐시 방지 필수)

# WebSocket 연결 관리
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


# ============ API Endpoints ============

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """대시보드 HTML 페이지 반환"""
    try:
        from fastapi.responses import Response
        html_file = BASE_DIR / "templates" / "index.html"
        
        if html_file.exists():
            # UTF-8로 읽기 (파일이 이미 UTF-8로 저장됨)
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return Response(
                content=content,
                media_type="text/html; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        else:
            logger.error(f"Dashboard template not found at: {html_file}")
            return HTMLResponse("<h1>Dashboard template not found</h1>")
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        import traceback
        traceback.print_exc()
        return HTMLResponse(f"<h1>Error loading dashboard</h1><pre>{str(e)}</pre>", status_code=500)





@app.get("/api/status")
async def get_status():
    """현재 자산 및 보유 종목 조회 (DB 기반 실시간 계산)"""
    try:
        from database_helpers import get_system_status, get_current_status, get_setting
        
        # 1. DB에서 현재 설정된 모드 확인
        use_mock = get_setting('use_mock_server', True)
        is_paper = get_setting('is_paper_trading', True)
        current_mode = "MOCK" if use_mock else "REAL"
        
        # 2. DB에서 최신 상태 조회 (현재 설정된 모드에 맞는 데이터만)
        bot_status = get_system_status(mode=current_mode)
        
        # 3. 데이터가 있고 내역의 모드가 현재 설정과 일치하면 반환
        if bot_status:
            summary = bot_status.get('summary', {})
            bot_api_mode = summary.get('api_mode', 'MOCK')
            bot_is_paper = summary.get('is_paper', True)
            
            # 모드가 정확히 일치할 때만 캐시 사용 (불일치 시 4번으로 넘어가서 즉시 재계산)
            if bot_api_mode.upper() == current_mode.upper() and bot_is_paper == is_paper:
                return bot_status

        # 4. 데이터가 없거나 모드가 바뀌었으면 DB에서 실시간으로 직접 계산 (강제 전환 효과)
        status = get_current_status(current_mode)
        
        # summary에 현재 설정값 명시 (프론트엔드 UI 갱신 도움)
        if 'summary' in status:
            status['summary']['api_mode'] = current_mode
            status['summary']['is_paper'] = is_paper
            
        return status
        
    except Exception as e:
        logger.error(f"상태 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'summary': {
                'total_asset': 0,
                'total_buy': 0,
                'deposit': 0,
                'total_pl': 0,
                'total_yield': 0,
                'bot_running': False,
                'api_mode': 'MOCK',
                'is_paper': True
            },
            'holdings': []
        }


@app.get("/api/sell-log")
async def get_sell_log():
    """매도 내역 조회 (DB에서 직접 조회)"""
    try:
        from database_trading_log import get_trading_logs_from_db
        
        from database_helpers import get_setting
        use_mock = get_setting('use_mock_server', True)
        is_paper = get_setting('is_paper_trading', True)
        
        if use_mock:
            mode = "MOCK"
        else:
            mode = "PAPER" if is_paper else "REAL"
        
        logger.info(f"📊 [API/sell-log] 모드 감지: {mode} (use_mock={use_mock}, is_paper={is_paper})")
        
        # DB에서 매도 내역만 조회 (오늘 날짜만)
        import datetime
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        
        data = get_trading_logs_from_db(mode=mode, limit=50, date=today_str)
        sells = data.get('sells', [])
        
        # 최신순 정렬
        sells.sort(key=lambda x: x.get('time', ''), reverse=True)
        
        return sells[:50]  # 최근 50건
        
    except Exception as e:
        logger.error(f"매도 로그 조회 실패: {e}")
        return []

@app.get("/api/trading-log")
async def get_trading_log(since_id: int = 0):
    """매매 내역 조회 (필터링된 리스트 + 전체 누계 통계)"""
    try:
        from database_trading_log import get_trading_logs_from_db, get_today_trading_stats
        from database_helpers import get_setting
        
        # 1. 현재 설정된 모드 확인 (설정 연동)
        use_mock = get_setting('use_mock_server', True)
        is_paper = get_setting('is_paper_trading', True)
        
        if use_mock:
            mode = "MOCK"
        else:
            mode = "PAPER" if is_paper else "REAL"
        
        logger.info(f"📊 [API/trading-log] 모드 감지: {mode} (use_mock={use_mock}, is_paper={is_paper})")
        
        import datetime
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # 2. 리스트 조회 (한 페이지용: 최신 100건, 오늘 날짜만)
        limit = 100 if since_id == 0 else 1000
        data = get_trading_logs_from_db(mode=mode, limit=limit, since_id=since_id, date=today_str)
        
        # 3. 전체 누계 통계 조회 (오늘 전체 대상)
        stats = get_today_trading_stats(mode=mode)
        data['stats'] = stats
        
        return data
        
    except Exception as e:
        logger.error(f"매매 로그 조회 실패: {e}") 
        return {"error": str(e), "buys": [], "sells": [], "stats": {"total": 0, "wins": 0, "total_profit": 0}}


@app.get("/api/settings")
async def get_settings():
    """설정 조회 (DB 전용)"""
    try:
        from database_helpers import get_all_settings
        settings = get_all_settings()
        return settings
    except Exception as e:
        logger.error(f"설정 조회 실패: {e}")
        return {}


@app.post("/api/settings")
async def update_settings(request: Request):
    """설정 변경 (DB 전용)"""
    try:
        from database_helpers import save_all_settings
        
        new_settings = await request.json()
        logger.info(f"📥 설정 저장 요청 받음: {new_settings.keys()}")
        # [DEBUG] 주요 필드 값 확인
        debug_keys = ['real_app_key', 'my_account', 'trading_mode']
        for k in debug_keys:
            if k in new_settings:
                logger.info(f"  - {k}: {new_settings[k]}")
        
        # DB에 저장
        save_all_settings(new_settings)
        
        # [환경 전환] 모드 전환 또는 API 키 변경 시 API 재초기화 및 봇 재부팅 신호
        auth_keys = ['use_mock_server', 'is_paper_trading', 'trading_mode', 'real_app_key', 'real_app_secret', 'paper_app_key', 'paper_app_secret']
        if any(k in new_settings for k in auth_keys):
            try:
                # 1. API 재초기화
                import kiwoom_adapter
                kiwoom_adapter.reset_api()
                logger.info(f"🔄 API 팩토리 초기화 완료 (모드/키 변경)")
                
                # 2. 봇 프로세스에 재시작(Re-init) 명령 전달
                from database_helpers import add_web_command
                add_web_command('reinit')
                logger.info(f"🚀 봇 재시작(Re-init) 명령 전달됨")
            except Exception as e:
                logger.error(f"⚠️ 봇 동기화 신호 전달 실패: {e}")
        
        logger.info(f"✅ 설정 저장 완료 및 동기화 신호 발송")
        return {"success": True, "message": "설정이 저장되었으며 시스템이 재시작됩니다."}
    except Exception as e:
        logger.error(f"❌ 설정 저장 실패: {e}")
        import traceback
        traceback.print_exc()


class CommandRequest(BaseModel):
    command: str


# 명령 큐 (봇이 polling해서 가져감)
COMMAND_FILE = BASE_DIR / "web_command.json"


@app.post("/api/command")
async def send_command(request: CommandRequest):
    """봇에 명령 전송 (start, stop, report, sellall)"""
    try:
        from database_helpers import add_web_command
        valid_commands = ['start', 'stop', 'report', 'sellall', 'status', 'reset']
        if request.command not in valid_commands:
            return {"success": False, "error": f"Invalid command: {request.command}"}
        
        # DB에 명령 저장
        if add_web_command(request.command):
            return {"success": True, "command": request.command, "message": f"'{request.command}' 명령이 전송되었습니다."}
        else:
            return {"success": False, "error": "DB 저장 실패"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/command")
async def get_command():
    """대기 중인 명령 조회 (봇에서 polling)"""
    try:
        from database_helpers import get_pending_web_command
        data = get_pending_web_command()
        if data:
            return data
    except Exception as e:
        pass
    return {"command": None}


@app.delete("/api/buy-log")
async def clear_buy_log():
    """매수 내역 삭제 (DB에서 삭제)"""
    try:
        from database_helpers import get_db_connection
        
        # 모드 확인
        mode = None
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    if settings.get("use_mock_server", True):
                        mode = "MOCK"
                    else:
                        is_paper = settings.get("is_paper_trading", True)
                        if is_paper: mode = "PAPER"
                        else: mode = "REAL"
            except:
                pass
        
        # DB에서 매수 내역 삭제
        with get_db_connection() as conn:
            if mode:
                conn.execute("DELETE FROM trades WHERE type='buy' AND mode=?", (mode,))
            else:
                conn.execute("DELETE FROM trades WHERE type='buy'")
            conn.commit()
        
        logger.info(f"매수 로그 삭제 완료 (mode={mode})")
        return {"success": True}
        
    except Exception as e:
        logger.error(f"매수 로그 삭제 실패: {e}")
        return {"success": False, "error": str(e)}


@app.delete("/api/sell-log")
async def clear_sell_log():
    """매도 내역 삭제 (DB에서 삭제)"""
    try:
        import sqlite3
        from database_helpers import get_db_connection
        
        # 모드 확인
        mode = None
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    if settings.get("use_mock_server", True):
                        mode = "MOCK"
                    else:
                        mode = "REAL"
            except:
                pass
        
        # DB에서 매도 내역 삭제
        with get_db_connection() as conn:
            if mode:
                conn.execute("DELETE FROM trades WHERE type='sell' AND mode=?", (mode,))
            else:
                conn.execute("DELETE FROM trades WHERE type='sell'")
            conn.commit()
        
        logger.info(f"매도 로그 삭제 완료 (mode={mode})")
        return {"success": True}
        
    except Exception as e:
        logger.error(f"매도 로그 삭제 실패: {e}")
        return {"success": False, "error": str(e)}


# ============ WebSocket ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 상태 업데이트 WebSocket"""
    await manager.connect(websocket)
    try:
        while True:
            # 0.5초마다 상태 전송
            try:
                from database_helpers import get_system_status
                data = get_system_status()
                if data:
                    await websocket.send_json(data)
            except Exception as e:
                pass # 연결 종료 등 예외 처리
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============ Run Server ============

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 정적 파일 서빙 시 캐시 방지 헤더 추가를 위한 미들웨어 또는 커스텀 라우트
@app.get("/static/{file_path:path}")
async def server_static(file_path: str):
    file = BASE_DIR / "static" / file_path
    if file.exists():
        return FileResponse(
            file, 
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return Response(status_code=404)
    
# ============ Window Title ============
import ctypes
if os.name == 'nt':
    ctypes.windll.kernel32.SetConsoleTitleW("Kiwoom Auto Trading Bot (Web Server)")

# ============ Bot Integration ============
import bot

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 봇 백그라운드 실행"""
    print("🤖 봇 시스템 초기화 및 시작...")
    
    async def run_bot_safe():
        try:
            bot_app = bot.MainApp()
            await bot_app.run()
        except Exception as e:
            msg = f"CRITICAL: 봇 실행 루프 종료됨: {e}"
            print(msg)
            logger.error(msg, exc_info=True)
            with open("startup_error.txt", "a") as f:
                f.write(f"{datetime.datetime.now()} - {msg}\n")
    
    try:
        # 1. 데이터베이스 초기화 (필수)
        from database import init_db
        await init_db()
        
        # 2. 봇 인스턴스 실행
        asyncio.create_task(run_bot_safe())
        
        print("✅ 봇 백그라운드 태스크 시작 완료")
    except Exception as e:
        print(f"❌ 봇 초기화 실패: {e}")
        with open("startup_error.txt", "a") as f:
            f.write(f"{datetime.datetime.now()} - 초기화 실패: {e}\n")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("[WEB] 웹 대시보드 서버 시작 (캐시 차단 모드)")
    print("   http://localhost:8080")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8080)
