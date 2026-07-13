"""
FastAPI 后端：将 Agent 接入 Web 页面
"""

import os
import sys
import json
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LLM_CONFIG
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage

# ── Agent 初始化 ─────────────────────────

@tool
def search_docs(query: str) -> str:
    """搜索知识库中与关键词匹配的文档，返回匹配的文件名和路径。"""
    try:
        from rag_engine import RAGEngine
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        engine = RAGEngine(repo_dir)
        results = engine.retrieve(query, top_k=10, mode="hybrid")
        if not results:
            return "没有找到匹配的文档。"
        lines = [f"找到 {len(results)} 个匹配结果：", ""]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['path']}")
            lines.append(f"   匹配度: {r['score']:.3f}")
        return "\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"

@tool
def pack_docs(query: str) -> str:
    """搜索匹配的文档并打包为 ZIP 压缩包，返回压缩包路径。"""
    try:
        from rag_engine import RAGEngine
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        engine = RAGEngine(repo_dir)
        results = engine.retrieve(query, top_k=20, mode="hybrid")
        if not results:
            return "没有找到匹配的文档。"
        import zipfile
        seen = set()
        files = []
        for r in results:
            if r["path"] not in seen:
                seen.add(r["path"])
                files.append(r["path"])
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in query)[:20].strip()
        zip_path = os.path.join(os.path.expanduser("~"), f"{safe or 'docs'}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                full = os.path.join(repo_dir, f)
                if os.path.exists(full):
                    zf.write(full, f)
        return f"打包完成！共 {len(files)} 个文件\n保存位置: {zip_path}"
    except Exception as e:
        return f"打包失败: {e}"

@tool
def current_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 加载 Agent
print("--- 初始化 Agent ---")
repo_dir = os.path.dirname(os.path.abspath(__file__))
try:
    from rag_engine import RAGEngine
    engine = RAGEngine(repo_dir)
    n = engine.index()
    print(f"[OK] 已索引 {n} 个文档片段")
except Exception as e:
    print(f"[WARN] 索引失败: {e}")

cfg = LLM_CONFIG.get("qwen", LLM_CONFIG["dashscope"])
llm = ChatOpenAI(
    model=cfg["model"],
    api_key=cfg.get("api_key"),
        base_url=cfg.get("base_url"),
)

tools = [search_docs, pack_docs, current_time]
system_prompt = (
    "你是一个AI复习资料提供助手，请用简洁明了的语句为用户解答疑惑，不需要丰富的感情，"
    "如果不清楚答案请直接回答不知道。"
)
memory = MemorySaver()
agent = create_agent(
    model=llm,
    tools=tools,
    checkpointer=memory,
    system_prompt=system_prompt,
)
print("[OK] Agent 已就绪")
print(f"    模型: {cfg['model']}")
print(f"    工具: {[t.name for t in tools]}")
print()

# ── FastAPI 应用 ─────────────────────────

app = FastAPI(title="复习资料助手")

# 挂载静态文件
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    thread_id = "web-session-1"
    config = {"configurable": {"thread_id": thread_id}}
    while True:
        try:
            data = await ws.receive_text()
            msg = json.loads(data)
            query = msg.get("query", "").strip()
            if not query:
                continue
            response = ""
            for chunk in agent.stream(
                {"messages": [HumanMessage(content=query)]},
                config,
                stream_mode="values",
            ):
                last = chunk["messages"][-1]
                if isinstance(last, AIMessage) and last.content:
                    response = last.content
            await ws.send_text(json.dumps({"reply": response}, ensure_ascii=False))
        except WebSocketDisconnect:
            break
        except Exception as e:
            await ws.send_text(json.dumps({"reply": f"错误: {e}"}, ensure_ascii=False))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
