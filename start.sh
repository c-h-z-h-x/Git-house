#!/bin/bash
# 复习资料助手 — 一键启动 (Mac/Linux)
cd "$(dirname "$0")"

echo ""
echo " === 复习资料助手 — 一键启动 ==="
echo ""

# 检查 Python
if ! command -v python3 &>/dev/null; then
    echo " [错误] 没找到 Python3！"
    echo " 请安装 Python 3.9+：https://www.python.org/downloads/"
    exit 1
fi
echo " Python: $(python3 --version)"

# 检查依赖
python3 -c "import fastapi, uvicorn, langchain_openai, pymupdf" 2>/dev/null
if [ $? -ne 0 ]; then
    echo " 正在安装依赖（首次需要等待）..."
    pip3 install -r requirements.txt -q
    if [ $? -ne 0 ]; then
        echo " [错误] 依赖安装失败！"
        exit 1
    fi
    echo " 依赖安装完成"
else
    echo " 依赖已就绪"
fi

echo ""
echo " 启动服务..."
echo " 浏览器访问: http://127.0.0.1:8000"
echo ""

# 自动打开浏览器
case "$(uname)" in
    Darwin) open http://127.0.0.1:8000 2>/dev/null ;;
    Linux)  xdg-open http://127.0.0.1:8000 2>/dev/null ;;
esac

python3 app.py
