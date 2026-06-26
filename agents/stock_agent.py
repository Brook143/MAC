from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, history_to_messages
from agents.tool_runner import run_tool_agent
from tools.fetch_data import fetch_stock_data


SYSTEM_PROMPT = """你是个股分析 Agent。你的任务是自己调用可用工具获取指定股票近十日行情数据，然后做客观分析。
要求：
1. 如果用户提供了股票代码，必须调用 fetch_stock_data 获取数据。
2. 如果用户没有提供标准代码，请自己思考对应的标准代码，例如 000001.SZ。
3. 只基于工具返回的数据分析，不编造行情。
4. 重点观察收盘价、涨跌幅、成交量、连续性。
5. 不给确定性买卖建议。"""


def run_stock_agent(user_id: str, user_msg: str, history=None) -> str:
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(history_to_messages(history))
    messages.append(HumanMessage(content=user_msg))
    result = run_tool_agent(
        llm=get_llm("stock"),
        tools=[fetch_stock_data],
        messages=messages,
    )
    return result or "请提供标准股票代码，例如 000001.SZ。"
