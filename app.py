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
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from openai import OpenAI

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
        seen = set()
        files = []
        for r in results:
            if r["path"] not in seen:
                seen.add(r["path"])
                files.append(r)
        lines = [f"找到 {len(files)} 个匹配结果：", ""]
        for i, r in enumerate(files, 1):
            lines.append(f"{i}. {r['path']}  (匹配度: {r['score']:.3f})")
            lines.append(f"   下载 →  /files/{r['path']}")
        return "\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"


@tool
def generate_exercises(subject: str) -> str:
    """根据学科关键词搜索复习资料，提取重点内容，生成 10 道填空题（含答案）。
    用法示例：\"生成线代填空题\"、\"出微积分的题\"、\"来点VA2的练习题\""""
    try:
        from rag_engine import RAGEngine, load_document
        from pathlib import Path

        engine = RAGEngine(REPO_DIR)

        # 1) 搜索相关文档
        results = engine.retrieve(subject, top_k=5, mode="hybrid")
        if not results:
            return "没有找到相关复习资料，无法生成习题。"

        # 2) 提取完整文档文本
        seen_files = set()
        all_text = ""
        for r in results:
            if r["path"] not in seen_files and len(all_text) < 8000:
                seen_files.add(r["path"])
                full_path = os.path.join(REPO_DIR, r["path"])
                if os.path.exists(full_path):
                    try:
                        text = load_document(Path(full_path), use_ocr=False)
                        if text:
                            all_text += f"\n--- {r['path']} ---\n{text[:3000]}\n"
                    except Exception:
                        pass

        if not all_text.strip():
            return "找到文档但无法提取文字内容。"

        # 3) 用 LLM 基于试卷知识点出概念填空题
        cfg = LLM_CONFIG.get("qwen", LLM_CONFIG["dashscope"])
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg.get("base_url"))

        sys_prompt = (
            "你是一个出题助手。根据以下复习资料（期中/期末试卷），制作 10 道概念填空题。\n"
            "要求：\n"
            "1. 题目围绕试卷中出现的核心概念、定义、公式、定理\n"
            "2. 每道题挖掉一个关键术语/数值/结论，用 ______ 表示\n"
            "3. 答案必须明确、唯一\n"
            "4. 覆盖不同知识点，避免重复\n"
            "5. 每条加上 source 字段标明参考自哪份试卷\n"
            "6. 用 JSON 输出，不要额外说明\n\n"
            '输出格式：\n'
            '{"title": "线性代数 概念填空题", "source": "参考来源", '
            '"questions": [{"id": 1, "question": "...______...", "answer": "..."}, ...]}'
        )

        user_prompt = f"请基于以下试卷内容，出 10 道概念填空题：\n\n{all_text[:6000]}"

        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        result_text = resp.choices[0].message.content.strip()
        parsed = json.loads(result_text)
        if "questions" not in parsed or len(parsed["questions"]) < 1:
            raise ValueError("生成的填空题格式异常")

        return result_text

    except json.JSONDecodeError:
        return '{"title":"出题失败","source":"","questions":[{"id":1,"question":"生成题目时格式错误，请重试","answer":""}]}'
    except Exception as e:
        return f"生成题目失败: {e}"


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
        tools = [search_docs, generate_exercises, current_time]
        system_prompt = (
            "你是一个AI复习资料提供助手。请用简洁明了的语句为用户解答疑惑。\n"
            "使用 search_docs 搜索复习资料，结果中自带下载链接。\n"
            "当用户要求生成练习题时，使用 generate_exercises 生成填空题。\n"
            "直接输出 /files/xxx 原始链接，不要用 Markdown 格式包裹它们。\n"
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
    resolved = os.path.normpath(os.path.join(REPO_DIR, path))
    if not resolved.startswith(os.path.normpath(REPO_DIR)):
        raise HTTPException(status_code=403, detail="禁止访问")
    if not os.path.isfile(resolved):
        raise HTTPException(status_code=404, detail="文件不存在")
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


@app.post("/api/exercises")
async def api_exercises(data: dict):
    """HTTP API: 生成填空题"""
    subject = data.get("subject", "").strip()
    if not subject:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "请输入学科关键词"}, status_code=400)

    try:
        from rag_engine import RAGEngine, load_document
        from pathlib import Path
        from openai import OpenAI

        engine = RAGEngine(REPO_DIR)
        results = engine.retrieve(subject, top_k=5, mode="hybrid")
        if not results:
            return {"error": "没有找到相关复习资料"}

        seen_files = set()
        all_text = ""
        for r in results:
            if r["path"] not in seen_files and len(all_text) < 8000:
                seen_files.add(r["path"])
                full_path = os.path.join(REPO_DIR, r["path"])
                if os.path.exists(full_path):
                    text = load_document(Path(full_path), use_ocr=False)
                    if text:
                        all_text += f"\n--- {r['path']} ---\n{text[:3000]}\n"

        cfg = LLM_CONFIG.get("qwen", LLM_CONFIG["dashscope"])
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg.get("base_url"))

        # 3) 基于试卷内容出概念填空题
        sys_prompt = (
            "你是一个出题助手。根据以下复习资料（期中/期末试卷），制作 10 道概念填空题。\n"
            "要求：\n"
            "1. 题目围绕试卷中出现的核心概念、定义、公式、定理\n"
            "2. 每道题挖掉一个关键术语/数值/结论，用 ______ 表示\n"
            "3. 答案必须明确、唯一\n"
            "4. 覆盖不同知识点，避免重复\n"
            "5. 用 JSON 输出，不要额外说明\n\n"
            '输出格式：\n'
            '{"title": "线性代数 概念填空题", "source": "参考来源", '
            '"questions": [{"id": 1, "question": "...______...", "answer": "..."}, ...]}'
        )

        user_prompt = f"请基于以下试卷内容，出 10 道概念填空题：\n\n{all_text[:6000]}"

        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        result = json.loads(resp.choices[0].message.content.strip())
        return result

    except Exception as e:
        return {"error": str(e)}


# ── WebSocket ──────────────────────────

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

            final_response = ""
            exercise_data = None

            for chunk in ag.stream(
                {"messages": [HumanMessage(content=query)]},
                config,
                stream_mode="values",
            ):
                last_msg = chunk["messages"][-1]

                # 检查是否是 generate_exercises 的工具返回结果
                if isinstance(last_msg, ToolMessage) and last_msg.name == "generate_exercises":
                    try:
                        parsed = json.loads(last_msg.content)
                        if isinstance(parsed, dict) and "questions" in parsed:
                            exercise_data = parsed
                    except (json.JSONDecodeError, TypeError):
                        pass

                # 记录最终 AI 回复
                if isinstance(last_msg, AIMessage) and last_msg.content:
                    final_response = last_msg.content

            if exercise_data:
                await ws.send_text(json.dumps({
                    "type": "exercise",
                    "title": exercise_data.get("title", "练习题"),
                    "source": exercise_data.get("source", ""),
                    "questions": exercise_data["questions"],
                    "reply": final_response,
                }, ensure_ascii=False))
            else:
                await ws.send_text(json.dumps({"reply": final_response}, ensure_ascii=False))

        except WebSocketDisconnect:
            break
        except Exception as e:
            await ws.send_text(json.dumps({"reply": f"错误: {e}"}, ensure_ascii=False))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
