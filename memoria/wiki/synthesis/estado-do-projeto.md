---
title: Estado do projeto
type: synthesis
sources: []
related: [[mas-mcp-server]], [[allowlist-somente-leitura]], [[automation-scripts-como-ferramentas]], [[chave-api-por-usuario]], [[doc-mcp-server]], [[guia-automation-scripts]]
created: 2026-10-21
updated: 2026-10-22
---

# Estado do projeto

Ler no início de cada sessão. Atualizar no fim.

## Onde paramos (2026-10-22)

`QUERYWORKORDERS` (1ª ferramenta de dados) escrito, testado localmente e
commitado (`d5998cf`). A 1ª instalação no Maximo de homologação mostrou problemas
no OAS; o script e o guia foram corrigidos. **Falta o usuário reinstalar** seguindo
`maximo_scripts/queryworkorders/INSTALACAO.md` e enviar:

1. trecho do `/api/oas?aitools=1` (passo 5), sem `u200b`;
2. saída do `check_connection` (passo 6);
3. as duas respostas de teste e a linha de log `param sources` (passo 7).

Com isso fechamos as perguntas abertas de [[automation-scripts-como-ferramentas]]
(origem dos parâmetros, `getUserInfo` no caminho MCP, `setTimestamp`, `datetime`
no Jython do Maximo).

## Feito

- 2026-10-21: esqueleto do repo, `uv sync`, pre-commit (gitleaks + Ruff), testes.
- 2026-10-21: `check_connection` corrigido (SDK mcp 2.3, UTF-8) e rodado contra
  homologação Itambé: conexão OK, só `apischema`.
- 2026-10-21: memória do projeto em `memoria/` (este wiki). Commit `24775f5`.
- 2026-10-22: ingest de [[doc-mcp-server]] e [[guia-automation-scripts]]
  (`docs/Automation_Scripts_IBM_Maximo.docx` versionado). Commit `48a1eed`.
- 2026-10-22: `maximo_scripts/queryworkorders/`: script Jython 2.7, response schema,
  README (especificação), `INSTALACAO.md` (passo a passo campo a campo) e 22 testes
  da lógica pura em `tests/unit/test_queryworkorders.py`. Commit `d5998cf`.
  - Filtros só por bind; colunas de listas fixas; limites no script (366 dias,
    50 wonum, 20 por lista, 500 por página); `total` sempre devolvido.
  - Permissão WOTRACK/READ e sites autorizados checados no código.
  - Lê parâmetros de variável literal, `requestBody` JSON ou query string.
- 2026-10-22: 1ª instalação no Maximo → OAS revelou: U+200B colado em nomes,
  `authapp`/`authsigoption` expostos como parâmetros, descrições cortadas em 100.
  Tudo corrigido no repositório.
- Ruff: `maximo_scripts/**` ignora `UP`, `B904`, `S608` (Jython 2.7).

## Git

Branch `chore/esqueleto-inicial`, 3 commits, **sem push**.

## Falta (ordem sugerida)

1. **Reinstalar `QUERYWORKORDERS`** e validar (ver "Onde paramos").
2. Implementar [[allowlist-somente-leitura]] em `src/maximo_agents/mcp/`:
   nome exato, rejeitar nomes não ASCII, descrição própria e rica de cada
   ferramenta, nunca repassar parâmetros fora do schema nosso.
3. Gateway de LLM em `llm/` com Ollama (não depende do Maximo; pode ir em paralelo).
4. Primeiro agente: laço com `QUERYWORKORDERS`, limite de 5 voltas.
5. Pequeno CLI `call_tool` para testar ferramentas sem MCP Inspector (opcional).
6. Quando o guia da Itambé voltar: novos scripts/filtros/campos e `tests/evals/`.
7. Trocar a chave MAXADMIN por chave de gerente e testar com usuário **sem** acesso
   a um site (checklist do README do script).

## Riscos ativos

- Chave MAXADMIN em homologação: ver [[chave-api-por-usuario]].
- 1ª versão do `QUERYWORKORDERS` no Maximo expõe `authapp`/`authsigoption` como
  parâmetros: manter **inativa** até a reinstalação.
- Não confirmado em runtime: imports `datetime`, `SqlFormat.setTimestamp`,
  `request.getUserInfo()` via MCP, paginação profunda com `getMbo(i)`.
