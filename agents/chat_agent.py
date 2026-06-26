from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, history_to_messages


SYSTEM_PROMPT = """你是一个友好、简洁的中文助手。
普通闲聊和常识问题请正常回答。
如果用户想分析股票，请提醒用户提供标准股票代码，例如 000001.SZ，或询问最近值得关注的股票。"""


def run_chat_agent(user_id: str, user_msg: str, history=None) -> str:
    try:
        msgs = [SystemMessage(content=SYSTEM_PROMPT)]
        msgs.extend(history_to_messages(history))
        msgs.append(HumanMessage(content=user_msg))
        msg = get_llm("chat").invoke(msgs)
        return msg.content.strip() if msg.content else "嗯，我在。"
    except Exception as exc:
        return f"闲聊 Agent 调用失败：{exc}"
