import os
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI


DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def history_to_messages(history):
    """把 dict 格式的会话历史转成 LangChain Message 对象列表。

    history 形如 [{"role": "user"|"assistant", "content": "..."}]。
    非法条目会被忽略，保证返回值可安全拼接到 LLM 的 messages 序列中。
    """
    result = []
    for item in history or []:
        role = item.get("role")
        content = item.get("content", "")
        if role == "user":
            result.append(HumanMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
    return result


def _env_for_agent(agent_name: str, suffix: str) -> str:
    return f"{agent_name.upper()}_{suffix}"


@lru_cache(maxsize=None)
def get_llm(agent_name: str = "default"):
    model = os.getenv(_env_for_agent(agent_name, "MODEL")) or os.getenv("DS_MODEL") or DEFAULT_MODEL
    api_key = os.getenv(_env_for_agent(agent_name, "API_KEY")) or os.getenv("DS_API_KEY")
    base_url = os.getenv(_env_for_agent(agent_name, "BASE_URL")) or os.getenv("DS_BASE_URL") or DEFAULT_BASE_URL
    if agent_name == "scanner":
        model = "deepseek-v4-pro"

    # router 是轻量意图判断，无需深度思考，省 token 和延迟
    enable_thinking = agent_name not in ("router",)

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        extra_body={"enable_thinking": enable_thinking},
    )
