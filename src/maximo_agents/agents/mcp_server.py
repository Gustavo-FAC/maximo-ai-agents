"""Servidor MCP local (stdio) com as análises do agente, para testes no Claude Code.

Só desenvolvimento: o Claude Code faz o papel do LLM, sem chave de API. O cliente vem
do TENANT_ID do .env (no produto, da sessão autenticada). As consultas script_* o
Claude Code já recebe do servidor "maximo" (com o hook da allowlist); aqui ficam só
as análises, que calculam em pandas e devolvem números prontos.

Uso (configurado em .mcp.json):
    uv run --no-sync python -m maximo_agents.agents.mcp_server
"""

import asyncio
import json
import logging
import sys
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from maximo_agents.agents.tools import ANALYSIS_TOOLS, CallTool, Toolbox
from maximo_agents.analysis.config import ClientConfig, load_client_config
from maximo_agents.config.settings import get_settings
from maximo_agents.mcp.session import MaximoSessionError, open_maximo_session

SERVER_NAME = "analises"

logger = logging.getLogger(__name__)

OpenSession = Callable[[], AbstractAsyncContextManager[CallTool]]


def _unavailable(message: str) -> dict:
    return {"error": {"code": "maximo_unavailable", "parameter": None, "message": message}}


def build_server(config: ClientConfig, open_session: OpenSession) -> Server:
    tools = [
        types.Tool(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in ANALYSIS_TOOLS.values()
    ]

    async def list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        try:
            async with open_session() as maximo:
                toolbox = Toolbox(maximo, config, ANALYSIS_TOOLS)
                result = await toolbox.run(params.name, params.arguments)
        except MaximoSessionError as e:
            result = _unavailable(str(e))
        except Exception:  # conexão: sem detalhe (URL, stack) para o LLM
            logger.exception("Maximo session failed")
            result = _unavailable("Could not connect to Maximo. Try again later.")
        text = json.dumps(result, ensure_ascii=False)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)], is_error="error" in result
        )

    return Server(SERVER_NAME, on_list_tools=list_tools, on_call_tool=call_tool)


async def serve() -> None:
    settings = get_settings()
    config = load_client_config(settings.tenant_id)
    server = build_server(config, lambda: open_maximo_session(settings))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> int:
    # stdout é o canal do protocolo: log só no stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    asyncio.run(serve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
