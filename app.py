"""
FastAPI 后端：将 Agent 接入 Web 页面
"""

import os
import sys
import json
import uuid
import threading
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

# ── 下载目录 ─────────────────────────────

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 启动时清理超过 1 小时的旧 zip 文件
import time as _time
try:
    now = _time.time()
    for f in os.listdir(DOWNLOAD_DIR):
        fp = os.path.join(DOWNLOAD_DIR, f)
        if f.endswith(".zip") and os.path.isfile(fp) and now - os.path.getmtime(fp) > 3600:
            os.remove(fp)
except Exception:
    pass

# ── 工具定义 ─────────────────────────────

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
        lines.append("")
        lines.append("💡 如需下载这些文件，回复「打包 + 关键词」即可")
        return "\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"

@tool
def pack_docs(query: str) -> str:
    """搜索匹配的文档并打包为 ZIP 压缩包，返回网页端可直接点击下载的链接。"""
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
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{safe or 'docs'}_{unique_id}.zip"
        zip_path = os.path.join(DOWNLOAD_DIR, filename)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                full = os.path.join(repo_dir, f)
                if os.path.exists(full):
                    zf.write(full, f)
        download_url = f"/download/{filename}"
        return f"📦 打包完成！共 {len(files)} 个文件\n点击下方链接下载：\n{download_url}"
    except Exception as e:
        return f"打包失败: {e}"

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
        tools = [search_docs, pack_docs, current_time]
        system_prompt = (
            "你是一个AI复习资料提供助手。请用简洁明了的语句为用户解答疑惑。\n"
            "你可以使用 search_docs 搜索文档，用 pack_docs 打包文档供用户下载。\n"
            "当用户找到想要的资料时，主动询问是否需要打包下载。\n"
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
        engine = RAGEngine(os.path.dirname(os.path.abspath(__file__)))
        n = engine.index()
        print(f"[后台] 索引完成: {n} 个片段", flush=True)
    except Exception as e:
        print(f"[后台] 索引失败: {e}", flush=True)
    finally:
        index_ready.set()

threading.Thread(target=_index_worker, daemon=True).start()

# ── FastAPI 应用 ─────────────────────────

app = FastAPI(title="复习资料助手")

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/download/{filename}")
async def download_file(filename: str):
    """提供 ZIP 文件下载（防路径穿越）"""
    import posixpath
    # 只取文件名部分，杜绝 ../../ 路径穿越
    safe_name = posixpath.basename(filename)
    file_path = os.path.join(DOWNLOAD_DIR, safe_name)
    if not os.path.exists(file_path):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "文件不存在或已过期"}, status_code=404)
    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
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
