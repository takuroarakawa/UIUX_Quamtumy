@echo off
chcp 65001 > nul
echo ============================================================
echo  Dr. CANVAS - AI セットアップ スクリプト
echo  AUTOMATIC1111 + Stable Diffusion WebUI
echo ============================================================
echo.

:: ── Python チェック ────────────────────────────────────────────
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python が見つかりません。
    echo https://www.python.org/downloads/release/python-3106/ からインストールしてください。
    pause & exit /b 1
)
echo [OK] Python が見つかりました。

:: ── Git チェック ───────────────────────────────────────────────
git --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git が見つかりません。
    echo https://git-scm.com/download/win からインストールしてください。
    pause & exit /b 1
)
echo [OK] Git が見つかりました。

:: ── AUTOMATIC1111 クローン ─────────────────────────────────────
set SD_DIR=C:\stable-diffusion-webui
if exist "%SD_DIR%" (
    echo [SKIP] AUTOMATIC1111 は既にインストール済み: %SD_DIR%
) else (
    echo [INFO] AUTOMATIC1111 をダウンロード中... (数分かかります)
    git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git "%SD_DIR%"
    if errorlevel 1 (
        echo [ERROR] クローンに失敗しました。ネット接続を確認してください。
        pause & exit /b 1
    )
    echo [OK] AUTOMATIC1111 をインストールしました。
)

:: ── start_sd.bat の生成 ────────────────────────────────────────
set START_SCRIPT=%SD_DIR%\start_drcanvas.bat
echo @echo off > "%START_SCRIPT%"
echo echo Dr. CANVAS 用 Stable Diffusion を起動中... >> "%START_SCRIPT%"
echo cd /d "%SD_DIR%" >> "%START_SCRIPT%"
echo call webui.bat --api --listen >> "%START_SCRIPT%"

echo.
echo ============================================================
echo  インストール完了！
echo.
echo  次のステップ:
echo  1. 漫画向けモデルを以下に配置してください:
echo     %SD_DIR%\models\Stable-diffusion\
echo     (推奨: Anything V5, CounterfeitXL)
echo.
echo  2. SD を起動するには:
echo     %START_SCRIPT%
echo     または: %SD_DIR%\webui.bat --api
echo.
echo  3. http://127.0.0.1:7860 で WebUI が開きます
echo  4. Dr. CANVAS の Phase 3 → SD設定 → 接続テスト
echo ============================================================
pause
