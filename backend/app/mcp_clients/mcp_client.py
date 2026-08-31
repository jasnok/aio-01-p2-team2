import asyncio
import json
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from backend.app.core.config import get_settings


def _mcp_servers() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    return {
        "food": {
            "transport": "streamable-http",
            "url": settings.food_mcp_url,
        }
    }


async def open_session(stack: AsyncExitStack, config: dict[str, Any]) -> ClientSession:
    if config["transport"] != "streamable-http":
        raise ValueError(f"지원하지 않는 MCP Transport입니다: {config['transport']}")

    read_stream, write_stream, _ = await stack.enter_async_context(
        streamable_http_client(config["url"])
    )
    session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
    await session.initialize()
    return session


@asynccontextmanager
async def mcp_sessions():
    async with AsyncExitStack() as stack:
        sessions: dict[str, ClientSession] = {}
        for server_name, config in _mcp_servers().items():
            sessions[server_name] = await open_session(stack, config)
        yield sessions


def result_text(result) -> str:
    return "\n".join(
        content.text for content in result.content if hasattr(content, "text")
    )


def _result_payload(result) -> dict[str, Any]:
    if result.isError:
        raise RuntimeError(result_text(result) or "MCP Tool 실행에 실패했습니다.")
    if result.structuredContent:
        return result.structuredContent

    text = result_text(result)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("MCP Tool이 JSON이 아닌 결과를 반환했습니다.") from error
    if not isinstance(payload, dict):
        raise ValueError("MCP Tool 결과는 JSON 객체여야 합니다.")
    return payload


async def discover_tools() -> list[dict[str, Any]]:
    timeout = get_settings().mcp_request_timeout_seconds
    async with asyncio.timeout(timeout):
        async with mcp_sessions() as sessions:
            tools: list[dict[str, Any]] = []
            for server_name, session in sessions.items():
                response = await session.list_tools()
                for tool in response.tools:
                    raw = tool.model_dump(by_alias=True)
                    tools.append(
                        {
                            "server": server_name,
                            "name": tool.name,
                            "public_name": f"{server_name}__{tool.name}",
                            "description": tool.description,
                            "input_schema": raw.get("inputSchema", {}),
                        }
                    )
            return tools


async def call_tool(server_name: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if server_name not in _mcp_servers():
        raise ValueError(f"등록되지 않은 MCP Server입니다: {server_name}")

    timeout = get_settings().mcp_request_timeout_seconds
    async with asyncio.timeout(timeout):
        async with mcp_sessions() as sessions:
            available = {tool.name for tool in (await sessions[server_name].list_tools()).tools}
            if tool_name not in available:
                raise ValueError(f"허용되지 않은 MCP Tool입니다: {tool_name}")
            result = await sessions[server_name].call_tool(tool_name, arguments=arguments)
            return _result_payload(result)


async def discover_resources() -> list[dict[str, Any]]:
    async with mcp_sessions() as sessions:
        resources: list[dict[str, Any]] = []
        for server_name, session in sessions.items():
            response = await session.list_resources()
            resources.extend(
                {
                    "server": server_name,
                    "name": resource.name,
                    "uri": str(resource.uri),
                    "description": resource.description,
                }
                for resource in response.resources
            )
        return resources


async def read_resource(server_name: str, uri: str) -> str:
    async with mcp_sessions() as sessions:
        response = await sessions[server_name].read_resource(uri)
    return "\n".join(
        content.text for content in response.contents if hasattr(content, "text")
    )
