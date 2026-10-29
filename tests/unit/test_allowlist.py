import importlib.util
import re
from pathlib import Path

import pytest

from maximo_agents.mcp.allowlist import (
    AGENT_TOOLS,
    MAX_ARGUMENT_LENGTH,
    QUERY_ASSETS,
    QUERY_WORK_ORDERS,
    ToolArgumentError,
    clean_arguments,
    input_schema,
    is_allowed,
)
from maximo_agents.mcp.claude_code_guard import check

SCRIPTS_DIR = Path(__file__).parents[2] / "maximo_scripts"


def load_script(folder, filename):
    path = SCRIPTS_DIR / folder / filename
    spec = importlib.util.spec_from_file_location(f"{folder}_for_allowlist", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qwo = load_script("queryworkorders", "QUERYWORKORDERS.py")
qa = load_script("queryassets", "QUERYASSETS.py")

# Descrição própria (allowlist) -> script que ela descreve.
SPEC_SCRIPTS = [(QUERY_WORK_ORDERS, qwo), (QUERY_ASSETS, qa)]
SPEC_IDS = [spec.name for spec, _ in SPEC_SCRIPTS]


@pytest.mark.parametrize("name", ["apischema", "script_queryworkorders", "script_queryassets"])
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
    assert set(AGENT_TOOLS) == set(SPEC_IDS)
    assert all(is_allowed(name) for name in AGENT_TOOLS)
    assert "apischema" not in AGENT_TOOLS


@pytest.mark.parametrize(("spec", "script"), SPEC_SCRIPTS, ids=SPEC_IDS)
def test_parametros_iguais_ao_script(spec, script):
    # Descrição própria não pode divergir do que o script aceita.
    assert list(spec.parameters) == list(script.PARAM_NAMES)
    assert spec.name == "script_" + script.__name__.split("_for_")[0]


@pytest.mark.parametrize(("spec", "script"), SPEC_SCRIPTS, ids=SPEC_IDS)
def test_campos_da_descricao_iguais_ao_script(spec, script):
    text = spec.parameters["fields"].split("Default:")[1]
    named = set(re.findall(r"[a-z]+", text)) & set(script.FIELD_TYPES)
    assert named == set(script.FIELD_TYPES)
    # Nenhum campo citado na descrição que o script não aceite.
    listed = re.findall(r"[a-z]+", text.split(". Also accepted:")[1].split(".")[0])
    default = re.findall(r"[a-z]+", text.split(". Also accepted:")[0])
    assert set(listed) | set(default) <= set(script.FIELD_TYPES)
    assert default == list(script.DEFAULT_FIELDS)


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
