import pytest

from maximo_agents.mcp.allowlist import is_allowed
from maximo_agents.mcp.claude_code_guard import check


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
