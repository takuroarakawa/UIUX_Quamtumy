@echo off
:: Dr. CANVAS — viewer ワンクリック起動
:: server.py が既に動いていればブラウザだけ開く

netstat -ano | findstr ":5174 " >nul 2>&1
if %errorlevel% == 0 (
    echo [Dr. CANVAS] サーバー起動済み
) else (
    echo [Dr. CANVAS] server.py を起動します...
    start "Dr.CANVAS server" /min cmd /c "cd /d "%~dp0" && python server.py"
    timeout /t 2 /nobreak >nul
)

start "" "http://127.0.0.1:5174/viewer.html"
