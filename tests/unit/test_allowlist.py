import importlib.util
import re
from pathlib import Path

import pytest

from maximo_agents.mcp.allowlist import (
    AGENT_TOOLS,
    MAX_ARGUMENT_LENGTH,
    QUERY_WORK_ORDERS,
    ToolArgumentError,
    clean_arguments,
    input_schema,
    is_allowed,
)
from maximo_agents.mcp.claude_code_guard import check

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "queryworkorders" / "QUERYWORKORDERS.py"
_spec = importlib.util.spec_from_file_location("queryworkorders_for_allowlist", SCRIPT)
qwo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qwo)


@pytest.mark.parametrize("name", ["apischema", "script_queryworkorders"])
def test_ferramentas_de_leitura_permitidas(name):
    assert is_allowed(name)


@pytest.mark.parametrize(
    "name",
    [
        "changestatus",
        "CHANGESTATUS",
        "createsr",
        "APISCHEMA",
        "script_queryworkorders​",
        "​script_queryworkorders",
        "",
    ],
)
def test_demais_ferramentas_bloqueadas(name):
    assert not is_allowed(name)


def test_guard_ignora_outros_servidores():
    assert check({"tool_name": "Bash"}) is None
    assert check({"tool_name": "mcp__outro__changestatus"}) is None


def test_guard_permite_allowlist():
    assert check({"tool_name": "mcp__maximo__script_queryworkorders"}) is None


def test_guard_bloqueia_fora_da_allowlist():
    assert check({"tool_name": "mcp__maximo__changestatus"}) is not None


def test_agentes_so_recebem_ferramentas_da_allowlist():
    assert AGENT_TOOLS
    assert all(is_allowed(name) for name in AGENT_TOOLS)
    assert "apischema" not in AGENT_TOOLS


def test_parametros_iguais_ao_script():
    # Descrição própria não pode divergir do que o script aceita.
    assert list(QUERY_WORK_ORDERS.parameters) == list(qwo.PARAM_NAMES)


def test_campos_da_descricao_iguais_ao_script():
    text = QUERY_WORK_ORDERS.parameters["fields"].replace(" and siteid", "")
    named = set(re.findall(r"[a-z]+", text.split("Default:")[1])) & set(qwo.FIELD_TYPES)
    assert named == set(qwo.FIELD_TYPES)


def test_descricoes_ascii_e_preenchidas():
    for spec in AGENT_TOOLS.values():
        assert spec.description.isascii()
        assert all(text.isascii() and text for text in spec.parameters.values())


def test_input_schema_fecha_parametros_extras():
    schema = input_schema(QUERY_WORK_ORDERS)
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(qwo.PARAM_NAMES)
    assert schema["properties"]["date_from"]["type"] == "string"


def test_clean_arguments_aceita_texto_e_inteiro():
    args = {"wonums": "1564759", "page_size": 5, "status": None}
    assert clean_arguments("script_queryworkorders", args) == {
        "wonums": "1564759",
        "page_size": "5",
    }


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("changestatus", {}),
        ("apischema", {}),
        ("script_queryworkorders\u200b", {}),
        ("script_queryworkorders", {"authapp": "WOTRACK"}),
        ("script_queryworkorders", {"wonums": ["1", "2"]}),
        ("script_queryworkorders", {"page": True}),
        ("script_queryworkorders", {"wonums": "1" * (MAX_ARGUMENT_LENGTH + 1)}),
    ],
)
def test_clean_arguments_recusa(tool, args):
    with pytest.raises(ToolArgumentError):
        clean_arguments(tool, args)
