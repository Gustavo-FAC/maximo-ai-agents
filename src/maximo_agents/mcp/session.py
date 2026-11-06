"""Sessão com o MCP Server do Maximo que só chama ferramentas de leitura da allowlist.

Entrega call_tool(nome, argumentos) -> dict (JSON da resposta do script). A chave
vai só no header; nunca aparece em mensagens de erro.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from maximo_agents.config.settings import Settings, get_settings
from maximo_agents.mcp.allowlist import is_allowed


class MaximoSessionError(RuntimeError):
    """Falha de configuração ou de chamada ao MCP Server (mensagem sem segredo)."""


@asynccontextmanager
async def open_maximo_session(settings: Settings | None = None) -> AsyncIterator:
    settings = settings or get_settings()
    api_key = settings.maximo_api_key.get_secret_value()
    if not settings.maximo_mcp_url or not api_key:
        raise MaximoSessionError("Set MAXIMO_MCP_URL and MAXIMO_API_KEY in .env.")

    async with create_mcp_http_client(headers={"apikey": api_key}) as http_client:
        async with streamable_http_client(settings.maximo_mcp_url, http_client=http_client) as (
            read,
            write,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()

                async def call_tool(name: str, arguments: dict[str, str]) -> dict:
                    if not is_allowed(name):
                        raise MaximoSessionError(f"Tool '{name}' is not in the allowlist.")
                    result = await session.call_tool(name, arguments)
                    text = "".join(getattr(part, "text", "") for part in result.content)
                    if result.is_error:
                        raise MaximoSessionError(f"{name} failed: {text[:500]}")
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError as e:
                        raise MaximoSessionError(f"{name} returned non-JSON content.") from e

                yield call_tool
