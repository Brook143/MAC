from agents.chat_agent import run_chat_agent
from agents.router import route
from agents.scanner_agent import run_scanner_agent
from agents.stock_agent import run_stock_agent


RISK_TEXT = (
    "风险提示：以上内容仅基于当前数据做客观分析，不构成投资建议。"
    "市场有风险，决策需谨慎。"
)

user_sessions = {}


def _get_session(user_id: str):
    if user_id not in user_sessions:
        user_sessions[user_id] = []
    return user_sessions[user_id]


def _trim_history(messages, max_messages=20):
    """保留最近 max_messages 条，并确保从 user 消息开始。

    直接取尾部可能让第一条落在 assistant 上，破坏 role 交替，
    部分模型会报错。这里裁掉开头的非 user 条目。
    """
    if len(messages) <= max_messages:
        return messages
    trimmed = list(messages[-max_messages:])
    while trimmed and trimmed[0].get("role") != "user":
        trimmed.pop(0)
    return trimmed


def _add_disclaimer(draft: str) -> str:
    """给非聊天类回复追加风险提示（不调用 LLM）。"""
    if not draft:
        return RISK_TEXT
    if "不构成投资建议" in draft:
        return draft
    return draft.rstrip() + "\n\n" + RISK_TEXT


def run_agent(user_id: str, user_msg: str) -> str:
    """
    多智能体入口：
    - router 负责判断任务类型
    - scanner_agent 负责股票筛选
    - stock_agent 负责个股分析
    - 非聊天类结果统一追加风险提示

    会话历史（之前的 user/assistant 轮次）会以快照形式注入各 agent，
    使其具备多轮上下文能力。当前 user_msg 不放入 history，由各 agent
    自行作为最后一条 HumanMessage 拼接，避免重复。
    """
    messages = _get_session(user_id)
    history = list(messages)  # 调用前的历史快照，不含当前这句

    task_type = route(user_msg, history)

    if task_type == "scan":
        draft = run_scanner_agent(user_id, user_msg, history)
    elif task_type == "stock":
        draft = run_stock_agent(user_id, user_msg, history)
    else:
        draft = run_chat_agent(user_id, user_msg, history)

    final = draft if task_type == "chat" else _add_disclaimer(draft)
    messages.append({"role": "user", "content": user_msg})
    messages.append({"role": "assistant", "content": final})
    user_sessions[user_id] = _trim_history(messages)
    return final
