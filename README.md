# Maximo AI Agents

Plataforma SaaS de agentes de IA para análise de ordens de serviço no IBM Maximo
(MAS 9.2), somente leitura. Cliente piloto: Itambé Cimentos.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `src/maximo_agents/config` | Configurações e dados dos tenants |
| `src/maximo_agents/auth` | Login próprio, MFA e sessões |
| `src/maximo_agents/llm` | Gateway de LLM (Claude ou LLM do cliente) |
| `src/maximo_agents/mcp` | Cliente MCP e allowlist de leitura |
| `src/maximo_agents/analysis` | Cálculo dos indicadores por código |
| `src/maximo_agents/agents` | Agentes, prompts e fluxos |
| `src/maximo_agents/api` | Endpoints usados pelo portal |
| `src/maximo_agents/audit` | Auditoria e medição de tokens |
| `maximo_scripts` | Fonte dos automation scripts instalados no Maximo |
| `tests` | Testes unitários, de isolamento e avaliações (evals) |
| `docs` | Arquitetura e guia de levantamento |

## Primeiros passos

1. Instale o [uv](https://docs.astral.sh/uv/) e o Python 3.12.
2. Instale as dependências: `uv sync`
3. Ative a verificação antes dos commits: `uv run pre-commit install`
4. Copie `.env.example` para `.env` e preencha os valores.
5. Teste a conexão com o Maximo: `uv run python -m maximo_agents.mcp.check_connection`
6. Rode os testes: `uv run pytest`

## Regras do projeto

- Nenhuma chave ou senha no repositório. Segredos ficam só no `.env` local.
- Somente leitura: nenhuma ferramenta que altere dados no Maximo é exposta aos agentes.
- Alterações na `main` apenas por pull request.
