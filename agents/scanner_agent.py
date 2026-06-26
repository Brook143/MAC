from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, history_to_messages
from agents.tool_runner import run_tool_agent
from tools.find_data import find_special_stocks


SYSTEM_PROMPT = """你是股票筛选 Agent。你的任务是自己调用可用工具获取特殊股票数据，然后客观整理值得关注的股票。
要求：
1. 必须优先调用 find_special_stocks 获取数据。
2. 不编造工具没有返回的数据。
3. 如果工具没有数据或工具失败，如实说明。
4. 用简洁结构输出。
5. 不给确定性买卖建议。"""


def run_scanner_agent(user_id: str, user_msg: str, history=None) -> str:
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(history_to_messages(history))
    messages.append(HumanMessage(content=user_msg))
    result = run_tool_agent(
        llm=get_llm("scanner"),
        tools=[find_special_stocks],
        messages=messages,
    )
    return result or "当前没有拿到特殊股票筛选结果。"
