"""Hook PreToolUse do Claude Code: aplica a allowlist ao servidor MCP "maximo".

Uso (configurado em .claude/settings.json):
    uv run --no-sync python -m maximo_agents.mcp.claude_code_guard

Lê o evento JSON da entrada padrão. Exit 2 bloqueia a chamada; qualquer erro
também bloqueia (falha fechada).
"""

import json
import sys

from maximo_agents.mcp.allowlist import is_allowed

SERVER_PREFIX = "mcp__maximo__"


def check(event: dict) -> str | None:
    """Retorna o motivo do bloqueio, ou None se a chamada é permitida."""
    tool_name = event.get("tool_name", "")
    if not tool_name.startswith(SERVER_PREFIX):
        return None
    name = tool_name.removeprefix(SERVER_PREFIX)
    if is_allowed(name):
        return None
    return f"Ferramenta '{name}' fora da allowlist de leitura do Maximo."


def main() -> int:
    try:
        reason = check(json.load(sys.stdin))
    except Exception as erro:  # noqa: BLE001
        reason = f"Falha ao validar a chamada ({type(erro).__name__}); bloqueada."
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
