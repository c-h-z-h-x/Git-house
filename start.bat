@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ═══════════════════════════════
echo    📚 复习资料助手 — 启动器
echo ═══════════════════════════════
echo.

:: 检查 Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [✗] 未找到 Python，请先安装 Python 3.9+
    echo     下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [✓] Python 已就绪

:: 检查 / 安装依赖
echo [~] 检查依赖...
python -c "import fastapi, uvicorn, langchain_openai, pymupdf" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [~] 正在安装依赖（首次运行需要等待）...
    pip install -r requirements.txt -q
    if %ERRORLEVEL% NEQ 0 (
        echo [✗] 依赖安装失败
        pause
        exit /b 1
    )
    echo [✓] 依赖安装完成
) else (
    echo [✓] 依赖已就绪
)

:: 启动服务并打开浏览器
echo.
echo [→] 正在打开浏览器...
start "" http://127.0.0.1:8000
echo [→] 启动服务器...
echo.
echo   按 Ctrl+C 停止服务
echo ═══════════════════════════════
echo.

python app.py

pause
