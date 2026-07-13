"""
LangChain Agent 示例
- 联网搜索
- 数学计算
- 可自由扩展工具
"""

from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from config import get_llm


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


# ── 主程序 ───────────────────────────────

def main():
    # 初始化 LLM
    llm = get_llm()

    # 组装工具
    tools = [
        DuckDuckGoSearchRun(),  # 联网搜索
        calculator,
        current_time,
    ]

    # 创建 Agent
    agent = create_tool_calling_agent(llm, tools)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
    )

    print("🤖 Agent 已启动！输入问题或 'exit' 退出\n")

    while True:
        query = input("你: ").strip()
        if query.lower() in ("exit", "quit", "q"):
            break
        if not query:
            continue

        result = agent_executor.invoke({"input": query})
        print(f"\n🤖: {result['output']}\n")


if __name__ == "__main__":
    main()
