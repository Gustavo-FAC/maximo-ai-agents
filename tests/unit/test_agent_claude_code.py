"""Camada de teste no Claude Code: servidor MCP local e subagente gerado da receita."""

import asyncio
import json
from contextlib import asynccontextmanager

from mcp import Client

from maximo_agents.agents.claude_agent import agent_path, claude_tool_name, render
from maximo_agents.agents.mcp_server import build_server
from maximo_agents.agents.recipes import WORK_ORDER_ANALYSIS
from maximo_agents.agents.tools import ANALYSIS_TOOLS
from maximo_agents.analysis.config import load_client_config
from maximo_agents.mcp.session import MaximoSessionError

CONFIG = load_client_config("itambe")


class FakeMaximo:
    def __init__(self):
        self.calls = []

    async def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        return {"total": 0, "items": [], "has_more": False}


def session_factory(maximo=None, error=None):
    @asynccontextmanager
    async def open_session():
        if error:
            raise error
        yield maximo

    return open_session


async def list_and_call(server, name, arguments):
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
        result = await client.call_tool(name, arguments)
    return tools, result


def test_server_lists_analyses_and_runs_them():
    maximo = FakeMaximo()
    server = build_server(CONFIG, session_factory(maximo))
    tools, result = asyncio.run(
        list_and_call(server, "analyze_corrective_recurrence", {"days": 30})
    )
    assert [t.name for t in tools] == list(ANALYSIS_TOOLS)
    assert tools[0].input_schema["additionalProperties"] is False
    assert not result.is_error
    report = json.loads(result.content[0].text)
    assert report["total"] == 0
    assert maximo.calls[0][1]["worktype"] == "CO,EM"


def test_server_returns_errors_as_tool_errors():
    server = build_server(CONFIG, session_factory(FakeMaximo()))
    _, result = asyncio.run(list_and_call(server, "analyze_material_usage", {"days": 0}))
    assert result.is_error
    assert json.loads(result.content[0].text)["error"]["code"] == "invalid_argument"

    # Consultas script_* não passam por aqui (vêm do servidor "maximo" com o hook).
    _, result = asyncio.run(list_and_call(server, "script_queryworkorders", {"wonums": "1"}))
    assert json.loads(result.content[0].text)["error"]["code"] == "unknown_tool"


def test_server_hides_connection_details():
    server = build_server(CONFIG, session_factory(error=OSError("https://host apikey=X")))
    _, result = asyncio.run(list_and_call(server, "analyze_material_usage", {}))
    text = result.content[0].text
    assert json.loads(text)["error"]["code"] == "maximo_unavailable"
    assert "apikey" not in text and "host" not in text

    server = build_server(CONFIG, session_factory(error=MaximoSessionError("Set MAXIMO_MCP_URL")))
    _, result = asyncio.run(list_and_call(server, "analyze_material_usage", {}))
    assert "MAXIMO_MCP_URL" in result.content[0].text


def test_claude_subagent_matches_recipe():
    text = render(WORK_ORDER_ANALYSIS, CONFIG)
    generated = agent_path(WORK_ORDER_ANALYSIS).read_text(encoding="utf-8")
    hint = "Rode: uv run python -m maximo_agents.agents.claude_agent"
    assert generated == text, hint
    header = text.split("---\n")[1]
    tools_line = next(line for line in header.splitlines() if line.startswith("tools: "))
    tools = tools_line.removeprefix("tools: ").split(", ")
    assert tools == [claude_tool_name(name) for name in WORK_ORDER_ANALYSIS.tools]
    assert "mcp__analises__analyze_material_usage" in tools
    assert "mcp__maximo__script_queryworkorders" in tools
    assert not any("querywomaterials" in t or "apischema" in t for t in tools)
    assert "Itambé Cimentos" in text and "CO, EM" in text


def test_client_context_states_currency_or_forbids_guessing():
    from dataclasses import replace

    from maximo_agents.agents.recipes import client_context

    assert "- Moeda dos custos: BRL." in client_context(CONFIG)
    without = client_context(replace(CONFIG, currency=None))
    assert "Moeda dos custos não informada" in without
    assert "BRL" not in without
