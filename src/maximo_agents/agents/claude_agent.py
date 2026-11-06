"""Gera o subagente do Claude Code a partir de uma receita (testes sem chave de API).

O subagente usa o mesmo prompt da receita (regras + contexto do cliente) e só as
ferramentas dela: análises pelo servidor local "analises" e consultas pelo servidor
"maximo". O arquivo é gerado; um teste garante que está igual à receita.

Uso:
    uv run python -m maximo_agents.agents.claude_agent [--client itambe] [--recipe analise-os]
"""

import argparse
import json
import sys
from pathlib import Path

from maximo_agents.agents.mcp_server import SERVER_NAME
from maximo_agents.agents.recipes import RECIPES, Recipe, client_context
from maximo_agents.agents.tools import ANALYSIS_TOOLS
from maximo_agents.analysis.config import ClientConfig, load_client_config

MAXIMO_SERVER = "maximo"  # nome em .mcp.json
AGENTS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "agents"


def claude_tool_name(name: str) -> str:
    server = SERVER_NAME if name in ANALYSIS_TOOLS else MAXIMO_SERVER
    return f"mcp__{server}__{name}"


def render(recipe: Recipe, config: ClientConfig) -> str:
    tools = ", ".join(claude_tool_name(name) for name in recipe.tools)
    # String JSON = string YAML entre aspas (a descrição tem ": ").
    description = json.dumps(f"{recipe.description} Cliente: {config.name}.", ensure_ascii=False)
    return (
        "---\n"
        f"name: {recipe.name}\n"
        f"description: {description}\n"
        f"tools: {tools}\n"
        "---\n\n"
        "<!-- Gerado por `python -m maximo_agents.agents.claude_agent`; não editar. -->\n\n"
        f"{recipe.instructions}\n\n{client_context(config)}\n"
    )


def agent_path(recipe: Recipe, agents_dir: Path = AGENTS_DIR) -> Path:
    return agents_dir / f"{recipe.name}.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m maximo_agents.agents.claude_agent")
    parser.add_argument("--client", default="itambe")
    parser.add_argument("--recipe", default="analise-os", choices=sorted(RECIPES))
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    recipe = RECIPES[args.recipe]
    path = agent_path(recipe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(recipe, load_client_config(args.client)), encoding="utf-8")
    print(f"Subagente gravado em {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
