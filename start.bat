@echo off
cd /d "%~dp0"
echo.
echo  === 复习资料助手 — 一键启动 ===
echo.
echo  第1步：检查 Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [错误] 没找到 Python！
    echo  请先安装 Python 3.9+，下载地址：
    echo  https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

echo  第2步：检查依赖...
python -c "import fastapi, uvicorn, langchain_openai, pymupdf" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo  [正在安装依赖，首次需要等待...]
    pip install -r requirements.txt -q
    if %ERRORLEVEL% NEQ 0 (
        echo  [错误] 依赖安装失败！
        pause
        exit /b 1
    )
    echo  依赖安装完成
) else (
    echo  依赖已就绪
)

echo.
echo  第3步：启动服务...
start http://127.0.0.1:8000
python app.py

pause
