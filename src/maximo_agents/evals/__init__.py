"""Evals dos agentes: perguntas de gerente com o comportamento esperado.

Os casos ficam em ``tests/evals/cases.toml``. O runner roda o grafo real (LLM do
gateway e MCP do Maximo), grava a conversa (ferramentas chamadas, argumentos,
resultados e resposta) e confere cada caso com regras determinísticas em
``checks.py``: ferramenta e argumentos certos, recusas, frases proibidas e números da
resposta vindos das ferramentas (a IA não faz contas). Sem LLM-juiz.

Uso:
    uv run python -m maximo_agents.evals --list
    uv run python -m maximo_agents.evals [--only ID,...] [--today AAAA-MM-DD]
"""
