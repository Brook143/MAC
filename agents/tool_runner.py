try:
    from langchain_core.messages import ToolMessage
except ImportError:
    class ToolMessage:
        def __init__(self, content: str, tool_call_id: str | None = None):
            self.content = content
            self.tool_call_id = tool_call_id


def run_tool_agent(llm, tools, messages, max_tool_calls=5) -> str:
    """Run an LLM tool-calling loop and return the final assistant content."""
    tool_map = {tool.name: tool for tool in tools}
    llm_with_tools = llm.bind_tools(tools)

    for _ in range(max_tool_calls):
        msg = llm_with_tools.invoke(messages)
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content.strip() if msg.content else ""

        for tool_call in msg.tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id")

            if tool_name not in tool_map:
                tool_result = f"错误：工具 {tool_name} 不存在"
            else:
                try:
                    tool_result = tool_map[tool_name].invoke(tool_args)
                except Exception as exc:
                    tool_result = f"工具 {tool_name} 执行失败：{exc}"

            messages.append(
                ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call_id,
                )
            )

    return f"已经连续调用了 {max_tool_calls} 轮工具，但还没有得到完整结果。请换个方式提问。"
