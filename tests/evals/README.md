# Evals dos agentes

Perguntas de gerente com o comportamento esperado do agente, rodadas no grafo real
(LLM do gateway + MCP do Maximo). Motor em `src/maximo_agents/evals/`; casos em
`cases.toml`.

```
uv run python -m maximo_agents.evals --list                  # lista, sem LLM
uv run python -m maximo_agents.evals                         # todos
uv run python -m maximo_agents.evals --only p33-backlog,g01-mps-semana
uv run python -m maximo_agents.evals --agent assistente-geral
uv run python -m maximo_agents.evals --today 2026-11-17      # data que o agente vê
```

Precisa de `LLM_PROVIDER`, `LLM_MODEL` (e a chave do provedor), `MAXIMO_MCP_URL` e
`MAXIMO_API_KEY` no `.env`. Saída 0 = todos passaram, 1 = algum falhou, 2 =
configuração. Relatório JSON em `reports/` (fora do git: tem dados do cliente).

## O que é conferido (sem LLM-juiz)

- `completed`: houve resposta, sem erro nem limite de rodadas.
- `calls`: ferramenta certa com os argumentos certos (argumento omitido vale o padrão
  da ferramenta; texto sem diferença de maiúsculas; lista como conjunto; `*` = qualquer).
- `forbidden_args` / `forbidden_tools` / `no_tools`: o que não pode ser chamado
  (ex.: `status=ACTIVE` no `script_querypms`; nenhuma ferramenta no prompt injection).
- `specialist`: no Assistente Geral, quem respondeu (`none` = ele mesmo).
- `answer_all` / `answer_any` / `answer_none`: regex na resposta. `[defaults]` proíbe
  em todos os casos nomes de ferramenta, arquivos, "apikey", "MCP" e "o senhor".
- `grounded_numbers`: todo número da resposta tem que estar na pergunta, nos argumentos
  ou nos resultados das ferramentas (com o arredondamento usado; x100 para %). Pega
  conta feita pelo LLM. Ignora datas, horas, códigos (MOI0001) e inteiros até 12.

Sem números fixos: os dados da homologação mudam. Casos com `gap` são perguntas do
guia sem ferramenta própria: o esperado hoje é não inventar número e dizer o que falta.
Quando a ferramenta existir, trocar a expectativa e apagar o `gap`.

Os testes do motor (modelo falso, sem rede) ficam em `tests/unit/test_evals.py`.
