"""Allowlist de ferramentas de leitura do MCP Server do Maximo.

Única barreira contra escrita: a flag "read only" do servidor não é garantia.
Nome exato, só ASCII (a 1ª instalação do QUERYWORKORDERS veio com U+200B colado).
"""

READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "apischema",
        "script_queryworkorders",
    }
)


def is_allowed(tool_name: str) -> bool:
    """Retorna True só para nomes ASCII presentes na allowlist."""
    return tool_name.isascii() and tool_name in READ_ONLY_TOOLS
