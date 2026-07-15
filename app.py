"""
FastAPI 后端：将 Agent 接入 Web 页面
"""

import os
import sys
import json
import threading
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 工具定义 ─────────────────────────────

@tool
def search_docs(query: str) -> str:
    """搜索知识库中与关键词匹配的文档，返回匹配的文件名和直接下载链接。"""
    try:
        from rag_engine import RAGEngine
        engine = RAGEngine(REPO_DIR)
        results = engine.retrieve(query, top_k=10, mode="hybrid")
        if not results:
            return "没有找到匹配的文档。"
        # 去重得到唯一文件列表
        seen = set()
        files = []
        for r in results:
            if r["path"] not in seen:
                seen.add(r["path"])
                files.append(r)
        lines = [f"找到 {len(files)} 个匹配结果：", ""]
        for i, r in enumerate(files, 1):
            lines.append(f"{i}. {r['path']}  (匹配度: {r['score']:.3f})")
            # 每个文件附上直接下载链接
            lines.append(f"   📥 /files/{r['path']}")
        return "\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"

@tool
def current_time() -> str:
    """获取当前时间"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── 全局 Agent（懒加载）───────────────────

agent = None
agent_lock = threading.Lock()

def get_agent():
    global agent
    if agent is not None:
        return agent
    with agent_lock:
        if agent is not None:
            return agent
        cfg = LLM_CONFIG.get("qwen", LLM_CONFIG["dashscope"])
        llm = ChatOpenAI(
            model=cfg["model"],
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
        )
        tools = [search_docs, current_time]
        system_prompt = (
            "你是一个AI复习资料提供助手。请用简洁明了的语句为用户解答疑惑。\n"
            "使用 search_docs 搜索复习资料，结果中自带下载链接，告知用户点击即可下载。\n"
            "如果不清楚答案请直接回答不知道，不需要丰富的感情。"
        )
        memory = MemorySaver()
        agent = create_agent(
            model=llm,
            tools=tools,
            checkpointer=memory,
            system_prompt=system_prompt,
        )
        return agent

# ── 后台索引 ──────────────────────────────

index_ready = threading.Event()

def _index_worker():
    print("[后台] 开始索引文档库...", flush=True)
    try:
        from rag_engine import RAGEngine
        engine = RAGEngine(REPO_DIR)
        n = engine.index()
        print(f"[后台] 索引完成: {n} 个片段", flush=True)
    except Exception as e:
        print(f"[后台] 索引失败: {e}", flush=True)
    finally:
        index_ready.set()

threading.Thread(target=_index_worker, daemon=True).start()

# ── FastAPI 应用 ─────────────────────────

app = FastAPI(title="复习资料助手")

static_dir = os.path.join(REPO_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/files/{path:path}")
async def serve_file(path: str):
    """直接从仓库提供原文件下载（防路径穿越）"""
    # 禁止路径穿越
    resolved = os.path.normpath(os.path.join(REPO_DIR, path))
    if not resolved.startswith(os.path.normpath(REPO_DIR)):
        raise HTTPException(status_code=403, detail="禁止访问")
    if not os.path.isfile(resolved):
        raise HTTPException(status_code=404, detail="文件不存在")
    # 用原文件名作为下载名（FileResponse 自动处理 Content-Disposition）
    return FileResponse(
        path=resolved,
        filename=os.path.basename(resolved),
    )


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/status")
async def status():
    return {"index_ready": index_ready.is_set()}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    if not index_ready.is_set():
        await ws.send_text(json.dumps({"reply": "知识库索引中，请稍候再试..."}, ensure_ascii=False))
        return

    ag = get_agent()
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
            for chunk in ag.stream(
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
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
