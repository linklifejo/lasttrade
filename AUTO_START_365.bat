@echo off
TITLE LASTTRADE AI 365 PERSISTENCE
:: 1분마다 start.py가 실행 중인지 확인하고, 없으면 실행합니다.
:loop
tasklist /FI "WINDOWTITLE eq LASTTRADE AI 365 PERSISTENCE" /NH | find /I "cmd.exe" > nul
if %errorlevel% equ 0 (
    :: 이미 실행 중인 프로세스 확인 (start.py)
    tasklist /V /FI "STATUS eq running" | find /I "python start.py" > nul
    if %errorlevel% neq 0 (
        echo [%date% %time%] AI Guardian is down. Reviving...
        start python start.py
    )
)
timeout /t 60 /nobreak > nul
goto loop
