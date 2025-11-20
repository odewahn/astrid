from typing import Optional, Callable, List, Any, Dict
import json

from openai.types.chat import ChatCompletionToolParam
import yaml

from fastmcp.exceptions import ToolError


def load_config(config_fn: str) -> dict:
    try:
        with open(config_fn, "r") as f:
            config_data = f.read()
            config = yaml.safe_load(config_data)
            # Normalize possible mcp keys to "mcpServers"
            for key in ["mcpServers", "mcp_servers", "mcpservers"]:
                if key in config:
                    config["mcpServers"] = config[key]
                    break
        return config
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {config_fn}: {e}")


# Converts MCP tool definitions to OpenAI chat tool format
def convert_mcp_tools_to_openai_format(
    mcp_tools_response: Any,
) -> List[ChatCompletionToolParam]:
    tools: List[ChatCompletionToolParam] = []
    for tool in mcp_tools_response:
        tools.append(
            ChatCompletionToolParam(
                type="function",
                function={
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                    or {
                        "type": "object",
                        "properties": {},
                    },
                },
            )
        )
    return tools


def safe_json_loads(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


async def run_tool(client, name: str, args: dict) -> str:

    try:
        result = await client.call_tool(name, args)
    except ToolError as e:
        raise RuntimeError(f"MCP tool '{name}' failed: {e}") from e

    if result.data is not None:
        return json.dumps(result.data, default=str)

    texts = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)

    if texts:
        return "\n".join(texts)

    return json.dumps(
        {
            "structured_content": result.structured_content,
            "is_error": getattr(result, "is_error", None),
        },
        default=str,
    )
