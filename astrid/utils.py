from typing import Optional, Callable, List, Any, Dict
import json
import git
import os
import shutil
import os
import base64
import json
from rich.prompt import Prompt


from Crypto.Protocol.KDF import scrypt as _scrypt
from Crypto.Cipher import AES

from openai.types.chat import ChatCompletionToolParam
import yaml

from fastmcp.exceptions import ToolError
from fastmcp import Client


def load_file(file_path: str) -> str:
    with open(file_path, "r") as f:
        return f.read()


def load_config(config_fn: str) -> dict:
    try:
        with open(config_fn, "r") as f:
            config_data = f.read()
            # Interpolate environment variables
            interpolated_string = os.path.expandvars(config_data)
            config = yaml.safe_load(interpolated_string)
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


async def discover_all_tools(config):
    all_tools = []
    # config["mcpServers"] is a dict of {name: server_cfg}
    for name, server_cfg in config.get("mcpServers", {}).items():
        single_cfg = {"mcpServers": {name: server_cfg}}
        try:
            async with Client(single_cfg) as c:
                server_tools = await c.list_tools()
                # Optionally prefix names with the server name to avoid collisions
                # This is only needed if there are multiple servers
                if len(config["mcpServers"]) > 1:
                    for t in server_tools:
                        t.name = f"{name}_{t.name}"
                all_tools.extend(server_tools)
        except Exception as e:
            raise Exception(f"[red]Failed to list tools from server {name}: {e}[/red]")
    return all_tools


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


def clone_repo(repo_url: str, dest_dir: str, overwrite: bool = False) -> None:

    if os.path.exists(dest_dir):
        if overwrite:
            # If the destination error exists and overwrite is true, remove it
            shutil.rmtree(dest_dir)
        else:
            # If the destination exists and overwrite is false, raise an error
            raise FileExistsError(f"Destination directory '{dest_dir}' already exists.")
    # Clone the repository
    try:
        repo = git.Repo.clone_from(
            repo_url,
            dest_dir,
            branch="main",
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to clone repository from {repo_url} to {dest_dir}: {e}"
        ) from e


"""
Helper to decrypt AES-GCM + Scrypt-wrapped env vars (ENC:... tokens).

Based on feature-encrypted-env-var.md pattern.
"""


b64d = lambda s: base64.urlsafe_b64decode(s.encode())


def derive_key(password: bytes, salt: bytes) -> bytes:
    # Match original scrypt parameters: N=2**15, r=8, p=1
    return _scrypt(password, salt, 32, N=2**15, r=8, p=1)


def load_and_decrypt_env(var_name: str = "ENCRYPTED_API_KEY") -> str:
    token = os.environ.get(var_name)
    if not token or not token.startswith("ENC:"):
        raise RuntimeError(f"{var_name} not set or not an ENC token")

    payload = json.loads(base64.urlsafe_b64decode(token[4:].encode()))
    if payload.get("v") != 1:
        raise RuntimeError("Unsupported secret version")

    salt = b64d(payload["s"])
    nonce = b64d(payload["n"])
    data = b64d(payload["c"])
    # Split out ciphertext and 16-byte GCM tag
    ct, tag = data[:-16], data[-16:]

    password = Prompt.ask("Password to unlock secret", password=True).encode()
    key = derive_key(password, salt)

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext = cipher.decrypt_and_verify(ct, tag)
    except ValueError:
        raise RuntimeError(
            "Failed to decrypt secret: incorrect password or corrupt token"
        )

    return plaintext.decode()
