"""模型配置：支持 OpenAI / 通义千问（工作空间）/ DeepSeek + RAG 引擎"""

import os
from dotenv import load_dotenv

load_dotenv()

# 阿里百炼工作空间
BAILIAN_BASE_URL = "https://ws-ogjwl5f71op9q2jf.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
BAILIAN_MODEL = "qwen-plus"

# 模型配置
LLM_CONFIG = {
    "openai": {
        "model": "gpt-4o-mini",
        "api_key": os.getenv("OPENAI_API_KEY"),
    },
    "qwen": {
        "model": "qwen-plus",
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "base_url": BAILIAN_BASE_URL,
    },
    "deepseek": {
        "model": "deepseek-chat",
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
        "base_url": "https://api.deepseek.com/v1",
    },
    "dashscope": {  # RAG 引擎专用（embedding 模型）
        "model": "qwen-plus",
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
        "base_url": BAILIAN_BASE_URL,
        "embed_model": "text-embedding-v3",
    },
}
