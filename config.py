"""模型配置：支持 OpenAI / 通义千问 / DeepSeek + RAG 引擎"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── 模型配置（供 agent.py 使用）────────────
LLM_CONFIG = {
    "openai": {
        "model": "gpt-4o-mini",
        "api_key": os.getenv("OPENAI_API_KEY"),
    },
    "qwen": {
        "model": "qwen-plus",
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "deepseek": {
        "model": "deepseek-chat",
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": "https://api.deepseek.com/v1",
    },
    "dashscope": {  # RAG 引擎专用（使用 embedding 模型）
        "model": "qwen-plus",
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
}

# ── 兼容旧的 baidu 配置名 ─────────────────
BAILIAN_API_KEY = os.getenv("DASHSCOPE_API_KEY")
BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
BAILIAN_MODEL = "qwen-plus"
