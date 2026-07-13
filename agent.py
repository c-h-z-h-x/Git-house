"""
对话式 Agent + RAG 知识库
- langgraph 对话记忆
- 从本地仓库检索 PDF/Word 文档内容
"""

import os

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from config import LLM_CONFIG


# -- 工具定义 -------------------------------

@tool
def query_codebase(question: str) -> str:
    """检索本地知识库（PDF/Word 文档），回答文档内容相关的问题。"""
    try:
        from rag_engine import RAGEngine
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        engine = RAGEngine(repo_dir)
        result = engine.query(question)
        return f"【回答】\n{result['answer']}\n\n【来源文件】\n" + "\n".join(f"- {s}" for s in result["sources"])
    except Exception as e:
        return f"查询知识库失败: {e}"


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


# -- 主程序 ---------------------------------

def main():
    print("--- 初始化中（索引知识库...） ---")

    try:
        from rag_engine import RAGEngine
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        engine = RAGEngine(repo_dir)
        n_chunks = engine.index()
        print(f"[OK] 已索引 {n_chunks} 个文档片段\n")
    except Exception as e:
        print(f"[WARN] 知识库索引失败: {e}（可继续对话，但文档检索不可用）\n")

    # 选择模型
    print("可用模型: openai / qwen / deepseek")
    model_choice = input("选择模型 [默认 qwen]: ").strip() or "qwen"

    cfg = LLM_CONFIG.get(model_choice)
    if not cfg:
        cfg = LLM_CONFIG["qwen"]

    llm = ChatOpenAI(
        model=cfg["model"],
        api_key=cfg.get("api_key"),
        base_url=cfg.get("base_url"),
    )

    tools = [query_codebase, calculator, current_time]

    # langgraph 带记忆的 Agent
    memory = MemorySaver()
    agent = create_agent(model=llm, tools=tools, checkpointer=memory)
    thread_id = "agent-session-1"

    print("\n" + "=" * 50)
    print(f"Agent 已启动（模型: {model_choice}）")
    print("  你可以：")
    print("  - 问知识库文档的内容 -> Agent 自动检索")
    print("  - 闲聊 -> Agent 记住上下文")
    print("  - 输入 exit / quit 退出")
    print("=" * 50 + "\n")

    while True:
        query = input("你: ").strip()
        if query.lower() in ("exit", "quit", "q"):
            print("拜拜")
            break
        if not query:
            continue

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
