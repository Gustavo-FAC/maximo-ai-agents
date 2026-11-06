import asyncio
import datetime
import json

import pytest

from maximo_agents.agents.recipes import WORK_ORDER_ANALYSIS
from maximo_agents.agents.tools import ANALYSIS_TOOLS, MAX_RESULT_CHARS, Toolbox
from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.fetch import MATERIAL_TOOL, WORK_ORDER_TOOL, MaximoToolError
from maximo_agents.mcp.allowlist import AGENT_TOOLS

CONFIG = load_client_config("itambe")
TODAY = datetime.date(2026, 11, 6)


class FakeMaximo:
    """call_tool falso: responde por nome de ferramenta e grava as chamadas."""

    def __init__(self, responses=None, error=None):
        self.responses = responses or {}
        self.error = error
        self.calls = []

    async def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        if self.error:
            raise self.error
        items = self.responses.get(name, [])
        return {"total": len(items), "items": items, "has_more": False}


def toolbox(maximo, names=WORK_ORDER_ANALYSIS.tools):
    return Toolbox(maximo, CONFIG, names, today=TODAY)


def run(coro):
    return asyncio.run(coro)


def test_definitions_cover_recipe_tools():
    definitions = toolbox(FakeMaximo()).definitions()
    names = [d["name"] for d in definitions]
    assert names == list(WORK_ORDER_ANALYSIS.tools)
    assert set(ANALYSIS_TOOLS) | set(AGENT_TOOLS) == set(names)
    for definition in definitions:
        schema = definition["input_schema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert definition["description"].isascii()  # descrições em inglês
    material = next(d for d in definitions if d["name"] == "analyze_material_usage")
    assert set(material["input_schema"]["properties"]) == {"days", "date_to", "top"}
    with pytest.raises(ValueError):
        toolbox(FakeMaximo(), names=["script_queryworkorders", "changestatus"])


def test_material_analysis_runs_with_period():
    maximo = FakeMaximo(
        {
            MATERIAL_TOOL: [
                {
                    "refwo": "100",
                    "siteid": "FABRICA",
                    "matusetransid": 1,
                    "actualdate": "2026-10-01T08:00:00",
                    "itemnum": "I1",
                    "description": "ROLAMENTO",
                    "quantity": -2,
                    "issueunit": "PC",
                    "linecost": 200.0,
                    "storeloc": "FAB",
                }
            ],
            WORK_ORDER_TOOL: [{"wonum": "100", "siteid": "FABRICA", "worktype": "CO"}],
        }
    )
    result = run(
        toolbox(maximo).run("analyze_material_usage", {"days": 30, "date_to": "2026-10-31"})
    )
    assert result["net_cost"] == 200.0
    assert (result["date_from"], result["date_to"]) == ("2026-10-02", "2026-10-31")
    assert list(result["by_worktype"]) == ["CO"]
    material_args = maximo.calls[0][1]
    assert (material_args["date_from"], material_args["date_to"]) == ("2026-10-02", "2026-10-31")
    assert maximo.calls[1][1]["wonums"] == "100"


def test_analysis_defaults_and_numbers_as_text():
    maximo = FakeMaximo()
    result = run(toolbox(maximo).run("analyze_corrective_recurrence", {"days": "90", "top": 5}))
    assert (result["date_from"], result["date_to"]) == ("2026-08-09", "2026-11-06")
    assert result["total"] == 0
    assert maximo.calls[0][1]["worktype"] == "CO,EM"


@pytest.mark.parametrize(
    "arguments",
    [
        {"days": 0},
        {"days": 731},
        {"days": "muitos"},
        {"days": True},
        {"date_to": "2026-11-07"},  # futuro
        {"date_to": "06/11/2026"},
        {"top": 51},
        {"siteid": "FABRICA"},  # parâmetro desconhecido
    ],
)
def test_invalid_analysis_arguments_never_reach_maximo(arguments):
    maximo = FakeMaximo()
    result = run(toolbox(maximo).run("analyze_corrective_recurrence", arguments))
    assert result["error"]["code"] == "invalid_argument"
    assert maximo.calls == []


def test_status_time_worktype_codes():
    maximo = FakeMaximo()
    box = toolbox(maximo)
    result = run(box.run("analyze_status_time", {"worktype": "CO, EM"}))
    assert result["worktypes"] == ["CO", "EM"]
    assert maximo.calls[0][1]["worktype"] == "CO,EM"
    too_many = ",".join(f"T{n}" for n in range(21))
    error = run(box.run("analyze_status_time", {"worktype": too_many}))["error"]
    assert error["code"] == "invalid_argument"


def test_query_tools_go_through_clean_arguments():
    maximo = FakeMaximo({WORK_ORDER_TOOL: [{"wonum": "1"}]})
    box = toolbox(maximo)
    result = run(box.run(WORK_ORDER_TOOL, {"wonums": "1", "page_size": 10}))
    assert result["total"] == 1
    assert maximo.calls == [(WORK_ORDER_TOOL, {"wonums": "1", "page_size": "10"})]

    bad = run(box.run(WORK_ORDER_TOOL, {"wonums": "1", "where": "1=1"}))
    assert bad["error"]["code"] == "invalid_argument"
    assert len(maximo.calls) == 1


def test_tools_outside_the_recipe_are_refused():
    maximo = FakeMaximo()
    box = toolbox(maximo, names=["analyze_material_usage"])
    for name in (WORK_ORDER_TOOL, "changestatus", "script_querywomaterials"):
        assert run(box.run(name, {}))["error"]["code"] == "unknown_tool"
    assert maximo.calls == []


def test_failures_become_safe_errors():
    maximo = FakeMaximo(error=MaximoToolError("range_too_large", "date_to", "too long"))
    result = run(toolbox(maximo).run("analyze_material_usage", {}))
    assert result["error"]["code"] == "range_too_large"
    assert result["error"]["parameter"] == "date_to"

    maximo = FakeMaximo(error=RuntimeError("apikey=SEGREDO stack trace"))
    result = run(toolbox(maximo).run(WORK_ORDER_TOOL, {"wonums": "1"}))
    assert result["error"]["code"] == "tool_failed"
    assert "SEGREDO" not in json.dumps(result)


def test_result_too_large():
    big = [{"wonum": str(n), "description": "x" * 100} for n in range(MAX_RESULT_CHARS // 100)]
    maximo = FakeMaximo({WORK_ORDER_TOOL: big})
    result = run(toolbox(maximo).run(WORK_ORDER_TOOL, {"wonums": "1"}))
    assert result["error"]["code"] == "result_too_large"
