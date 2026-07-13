"""
🤖 对话式 Agent + RAG 代码知识库
- 用 langgraph 管理对话记忆
- 可从自己的代码仓库中检索信息回答问题
"""

import os

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from config import LLM_CONFIG


# ── 工具定义 ─────────────────────────────

@tool
def calculator(expression: str) -> str:
    """计算数学表达式，如 '2 + 3 * 4'"""
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"计算错误: {e}"


@tool
def current_time() -> str:
    """获取当前时间"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def query_codebase(question: str) -> str:
    """检索当前项目的代码仓库，回答关于项目代码的问题。
    
    用法示例：
    - "这个项目的结构是什么？"
    - "agent.py 里有哪些工具？"
    - "config.py 支持哪些模型？"
    """
    try:
        from rag_engine import RAGEngine
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        engine = RAGEngine(repo_dir)
        result = engine.query(question)
        return f"【回答】\n{result['answer']}\n\n【来源文件】\n" + "\n".join(f"- {s}" for s in result["sources"])
    except Exception as e:
        return f"查询代码库失败: {e}"


# ── 主程序 ───────────────────────────────

def main():
    print("--- 初始化中（索引代码库...） ---")

    # 初始化 RAG 引擎
    try:
        from rag_engine import RAGEngine
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        engine = RAGEngine(repo_dir)
        n_chunks = engine.index()
        print(f"[OK] 已索引 {n_chunks} 个代码片段\n")
    except Exception as e:
        print(f"[WARN] RAG 索引失败: {e}（可继续对话，但代码检索不可用）\n")

    # 选择模型
    print("可用模型: openai / qwen / deepseek")
    model_choice = input("选择模型 [默认 qwen]: ").strip() or "qwen"

    cfg = LLM_CONFIG.get(model_choice)
    if not cfg:
        cfg = LLM_CONFIG["qwen"]

    llm = ChatOpenAI(
        model=cfg["model"],
        api_key=cfg["api_key"],
        base_url=cfg.get("base_url"),
    )

    # 工具集
    tools = [
        query_codebase,      # RAG 代码检索
        calculator,
        current_time,
    ]

    # 联网搜索（可选）
    try:
        search = DuckDuckGoSearchRun()
        tools.append(search)
        print("[OK] 联网搜索已启用")
    except Exception:
        pass

    # 用 langgraph 创建带记忆的 Agent
    memory = MemorySaver()
    agent = create_agent(model=llm, tools=tools, checkpointer=memory)
    thread_id = "agent-session-1"

    print("\n" + "=" * 50)
    print(f"Agent 已启动（模型: {model_choice}）")
    print("  你可以：")
    print("  - 问代码项目的问题 -> Agent 会检索仓库内容")
    print("  - 闲聊 -> Agent 会记住上下文")
    print("  - 输入 exit / quit 退出")
    print("=" * 50 + "\n")

    while True:
        query = input("你: ").strip()
        if query.lower() in ("exit", "quit", "q"):
            print("拜拜")
            break
        if not query:
            continue

        # langgraph 自动维护对话历史
        response = ""
        config = {"configurable": {"thread_id": thread_id}}
        for chunk in agent.stream(
            {"messages": [HumanMessage(content=query)]},
            config,
            stream_mode="values",
        ):
            last_msg = chunk["messages"][-1]
            if isinstance(last_msg, AIMessage) and last_msg.content:
                response = last_msg.content

        print(f"\nAI: {response}\n")


if __name__ == "__main__":
    main()
