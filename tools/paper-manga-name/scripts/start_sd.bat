@echo off
chcp 65001 > nul
echo ============================================================
echo  Dr. CANVAS - Stable Diffusion 起動
echo  API モードで起動します (Dr. CANVAS から自動接続)
echo ============================================================
echo.

set SD_DIR=C:\stable-diffusion-webui
if not exist "%SD_DIR%\webui.bat" (
    echo [ERROR] AUTOMATIC1111 が見つかりません。
    echo まず install_sd.bat を実行してください。
    pause & exit /b 1
)

echo [INFO] SD を起動中... ブラウザが開いたら Dr. CANVAS を使用できます。
echo [INFO] 終了するには Ctrl+C を押してください。
echo.
cd /d "%SD_DIR%"
call webui.bat --api --listen
