"""意图路由智能体。

优先用 LLM 判断用户意图（可结合对话历史消歧指代词），
LLM 不可用时自动回退到关键词规则路由，保证可用性。
"""
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm, history_to_messages

logger = logging.getLogger(__name__)

# ---- 规则兜底用 ----
# 用前后非 ASCII 单词字符断言替代 \b，避免中文紧贴代码时失效
# （Python3 的 \w 默认含中文，故显式用 A-Za-z0-9_ 字符集）
STOCK_CODE_RE = re.compile(r"(?<![A-Za-z0-9_.])\d{6}\.(SZ|SH|BJ)(?![A-Za-z0-9_.])", re.IGNORECASE)
SCAN_KEYWORDS = ["推荐", "筛选", "异动", "值得关注", "股票池", "特殊股票"]

VALID_TYPES = ("stock", "scan", "chat")

SYSTEM_PROMPT = """你是一个意图路由智能体。根据用户当前消息（以及可选的对话历史）判断用户意图，只返回以下三个标签之一，不要输出任何其他内容：

- stock：用户想分析、查询某只具体股票（包含股票代码，或明确提到某只股票的名字/简称，或上下文中正在分析某只个股且用户在追问它）
- scan：用户想要筛选、发现、推荐值得关注的股票（如"最近有什么""推荐几只""有哪些特殊股票""股票池""异动"）
- chat：普通闲聊、常识问题、与股票无关的问题，或意图不明确

判断规则：
1. 明确包含 6 位股票代码（如 000001.SZ）一定是 stock。
2. "继续""那它呢""再说说"这类指代词，必须结合历史最后一条实质内容判断正在讨论什么：若上一轮在分析个股则 stock，在选股则 scan，否则 chat。
3. 模糊时倾向 chat，不要瞎猜。
4. 只输出一个单词：stock 或 scan 或 chat，不要加标点、不要解释。"""


def _rule_route(user_msg: str) -> str:
    """规则兜底路由（LLM 不可用或显式回退时使用）。"""
    text = user_msg or ""
    if STOCK_CODE_RE.search(text):
        return "stock"
    if any(kw in text for kw in SCAN_KEYWORDS):
        return "scan"
    return "chat"


def _parse_route_response(text: str) -> str:
    """从 LLM 回复中提取标签。

    LLM 被要求只输出一个单词，但做容错：取首个命中的有效标签，
    都不命中则回退 chat（最安全的默认）。
    """
    if not text:
        return "chat"
    t = text.strip().lower()
    for tag in VALID_TYPES:
        if tag in t:
            return tag
    return "chat"


def route(user_msg: str, history=None) -> str:
    """智能体路由入口。

    策略（三层）：
      1. 快速路径：消息含明确股票代码 → 直接 stock，跳过 LLM
      2. LLM 路由：注入最近少量历史帮助消歧指代词，让 LLM 判意图
      3. 兜底：LLM 调用失败 → 回退关键词规则

    Args:
        user_msg: 当前用户消息
        history: 对话历史快照（dict 列表，形如 [{"role":"user","content":"..."}]），
                 用于消歧"继续""那它呢"等指代词。可为 None。

    Returns:
        "stock" | "scan" | "chat"
    """
    # 1. 快速路径：明确股票代码，无需调 LLM
    if STOCK_CODE_RE.search(user_msg or ""):
        return "stock"

    # 2. LLM 智能路由
    try:
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        # 注入最近 4 条历史帮助消歧，控制 token 开销
        if history:
            messages.extend(history_to_messages(history[-4:]))
        messages.append(HumanMessage(content=user_msg or ""))

        resp = get_llm("router").invoke(messages)
        raw = getattr(resp, "content", "")
        tag = _parse_route_response(raw)
        logger.debug("router LLM -> %s (raw: %r)", tag, raw)
        return tag
    except Exception as e:
        # 3. 兜底回退规则
        logger.warning("router LLM 调用失败，回退规则路由: %s", e)
        return _rule_route(user_msg)
