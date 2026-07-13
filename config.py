"""模型配置：切换模型只需改这里的 MODEL 变量"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# ── 在这里切换模型 ──────────────────────
# 可选: "openai" / "qwen" / "deepseek"
MODEL = "qwen"
# ───────────────────────────────────────

def get_llm():
    if MODEL == "openai":
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    elif MODEL == "qwen":
        return ChatOpenAI(
            model="qwen-plus",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    elif MODEL == "deepseek":
        return ChatOpenAI(
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
        )
    else:
        raise ValueError(f"不支持的模型: {MODEL}")
