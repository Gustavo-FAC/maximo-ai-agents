---
title: Estado do projeto
type: synthesis
sources: []
related: [[mas-mcp-server]], [[allowlist-somente-leitura]], [[automation-scripts-como-ferramentas]], [[chave-api-por-usuario]], [[doc-mcp-server]], [[guia-automation-scripts]]
created: 2026-10-21
updated: 2026-10-30
---

# Estado do projeto

Ler no início de cada sessão. Atualizar no fim.

## Onde paramos (2026-10-30)

- **Roteiro de testes:** 32 prompts de OS e ativos em [[prompts-de-teste]] para o
  usuário testar no Claude Code; semente de `tests/evals/`.
- **`.mcp.json` não conectou** nesta sessão (`'url' is not a valid URL`): Claude
  Code aberto sem `MAXIMO_MCP_URL`/`MAXIMO_API_KEY` no ambiente. Abrir por
  `scripts/claude-maximo.ps1`. Conector `maximo` do claude.ai seguiu ativo
  (`script_queryworkorders`, `script_queryassets`).
- Push da `main` feito (sincronizada com `origin/main`). `feat/queryworkorders-text`
  ainda existe localmente (pode apagar).
- `virtualenv` 21.15.1 no `uv.lock` (alerta do Dependabot); commit na `main`.
- **`QUERYFAILUREREPORTS` cancelado:** Itambé não usa classe de falha (consultor
  funcional). Ver [[ferramentas-maximo]].
- **`text` no `QUERYWORKORDERS` funcionando via MCP** (bloco comum, 15 parâmetros,
  sem `u200b`). "vazamento" → 92 OS em 12 meses; "vazamento oleo" → 3; erros ok;
  sem `text` igual a antes (18337). `QUERYASSETS` reinstalado com o bloco novo,
  mesmo resultado de 2026-10-29. Branch `feat/queryworkorders-text` integrada na
  `main` (sem push).
- **Achados nos dados (perguntar ao consultor):** tipo de trabalho corretivo é
  **CO** (não CM); 34 de 92 OS com "vazamento" **sem `worktype`**; muitas OS são
  itens de checklist ("NÃO CONFORME: HÁ VAZAMENTO NA TUBULAÇÃO?"). Contagem de
  falhas por palavra mistura inspeção com falha real. Ver [[itambe-cimentos]].
- **Pendente do usuário no Maximo:** Log Level do `QUERYWORKORDERS` de volta para
  ERROR; Description do script difere do `INSTALACAO.md` (antiga, sem "or wonums";
  não afeta o agente).
- **Próximo passo:** usuário decide ao retomar (gateway de LLM segue em espera;
  opções de script: histórico de status, `QUERYJOBPLANS`).

## Antes (2026-10-29, fim)

- **Novas ferramentas antes do gateway** (decisão do usuário): plano em
  [[ferramentas-maximo]]. `QUERYASSETS` na `main`, **instalado e
  validado via MCP** (14709 ativos, filtros, `text`, hierarquia, paginação, erros).
  Achado: `ancestor` trazia o próprio ativo (linha dele com ele mesmo em
  ASSETANCESTOR); corrigido no SQL, reinstalado e conferido (CCM2.1 → 21).
  **Próximo passo (sessão de 2026-10-30):** `QUERYFAILUREREPORTS` (FAILUREREPORT +
  WORKORDER, datas obrigatórias, WOTRACK/READ, bloco comum copiado), em branch nova;
  depois `text` no `QUERYWORKORDERS` (que então recebe o bloco comum).
- Teste sem reiniciar o Claude Code: cliente avulso no scratchpad chama ferramentas
  da allowlist (o Claude Code só vê ferramentas registradas antes do início da
  sessão). Item "CLI `call_tool`" de "Falta" ganha motivo.
- **`QUERYWORKORDERS` funcionando via MCP** em homologação (Claude Code → MCP Server
  → script): dados reais, paginação, filtros, validações e busca por `wonums` sem
  datas conferidos. Detalhes em [[automation-scripts-como-ferramentas]].
- **Allowlist pronta para o agente:** descrições próprias para o LLM,
  `input_schema` fechado e `clean_arguments` ([[allowlist-somente-leitura]]).
- 101 testes, Ruff e pre-commit ok.
- **Gateway de LLM em espera:** usuário ainda analisando a abordagem. Não começar
  sem decisão dele. Por isso o 1º agente também espera.

## Git

GitHub `Gustavo-FAC/maximo-ai-agents` (privado). 2026-10-30:
`feat/queryworkorders-text` integrada na `main` por fast-forward, com push
(`main` sincronizada). Branch ainda existe localmente. `chore/esqueleto-inicial` foi
integrada por fast-forward e apagada (local e remoto) em 2026-10-29.
`feat/queryassets` integrada na `main` por fast-forward em 2026-10-29, com push
(feito pelo usuário). Branch apagada. Só a `main`, sincronizada. Trabalho novo: branch nova a partir da `main`.

## Feito

- 2026-10-21: esqueleto do repo, `uv sync`, pre-commit (gitleaks + Ruff), testes.
- 2026-10-21: `check_connection` corrigido (SDK mcp 2.3, UTF-8) e rodado contra
  homologação Itambé: conexão OK, só `apischema`.
- 2026-10-21: memória do projeto em `memoria/` (este wiki).
- 2026-10-22: ingest de [[doc-mcp-server]] e [[guia-automation-scripts]].
- 2026-10-22: `maximo_scripts/queryworkorders/`: script Jython 2.7, response schema,
  README (especificação), `INSTALACAO.md` e testes da lógica pura.
  - Filtros só por bind; colunas de listas fixas; limites no script (366 dias,
    50 wonum, 20 por lista, 500 por página); `total` sempre devolvido.
  - Permissão WOTRACK/READ e sites autorizados checados no código.
- 2026-10-22: 1ª instalação → OAS revelou U+200B colado em nomes,
  `authapp`/`authsigoption` expostos como parâmetros, descrições cortadas em 100.
  Corrigido.
- Ruff: `maximo_scripts/**` ignora `UP`, `B904`, `S608` (Jython 2.7).
- 2026-10-29: Claude Code ligado ao MCP do Maximo: `.mcp.json` (URL e chave por
  variável de ambiente), `scripts/claude-maximo.ps1`, allowlist de nomes exatos e
  hook `claude_code_guard.py` (fail-closed); settings negam as 7 ferramentas padrão
  de escrita.
- 2026-10-29: `QUERYWORKORDERS` posto para rodar no Maximo. Sequência de erros e
  correções (detalhes em [[automation-scripts-como-ferramentas]]):
  1. BMXAA10147E com usuário da chave em PT → usuário em EN (observação em
     [[mas-mcp-server]], não pré-requisito).
  2. `No module named datetime` → classe `Day` própria (Jython sem biblioteca padrão).
  3. Resposta toda `null` → `OslcUtils.jsonToBytes` e variáveis implícitas lidas do
     escopo.
  4. HTTP 500 BMXAA1649E → `StackOverflowError` por `_scope = globals()` no topo;
     lógica movida para `_main`.
  5. `internal_error` → `ScriptService` sem `isLoggingEnabled`; removido.
- 2026-10-29: datas opcionais quando `wonums` vem preenchido (decisão do usuário),
  reinstalado e validado.
- 2026-10-29: allowlist com descrições próprias, `input_schema` e
  `clean_arguments`; `apischema` só no Claude Code, fora dos agentes.
- 2026-10-29: merge na `main`, push, branch antiga apagada.
- 2026-10-29: `QUERYASSETS` escrito, instalado, validado via MCP; `ancestor` sem o
  próprio ativo. `feat/queryassets` integrada na `main`, com push.
- 2026-10-30: `virtualenv` 21.14.12 → 21.15.1 (Dependabot, alta); 92 testes e
  pre-commit ok.
- 2026-10-30: `QUERYFAILUREREPORTS` cancelado (Itambé não usa classe de falha).
- 2026-10-30: `text` no `QUERYWORKORDERS`; `QUERYWORKORDERS` no bloco comum
  (`parse_text`/`add_text_filter` passaram para o bloco). Antigo e novo comparados
  com as mesmas entradas: mesmo SQL, binds e erros. 101 testes. Validado via MCP.

## Falta (ordem sugerida)

1. Gateway de LLM em `llm/`: **aguardando decisão do usuário**.
2. Primeiro agente: laço com `QUERYWORKORDERS`, limite de 5 voltas, usando
   `AGENT_TOOLS`, `input_schema` e `clean_arguments`.
3. Linha DEBUG `implicit vars` do log do Manage (origem dos parâmetros e da
   identidade no caminho MCP). Só registro; não bloqueia nada.
4. Pequeno CLI `call_tool` para testar ferramentas sem MCP Inspector (opcional).
5. Quando o guia da Itambé voltar: novos scripts/filtros/campos e `tests/evals/`.
6. Trocar a chave MAXADMIN por chave de gerente e testar com usuário **sem** acesso
   a um site (checklist do README do script).
7. Análises com conta (ex.: OS por ativo, tempo médio) vão para `analysis/` (a IA
   não faz contas); hoje a ferramenta só dá totais por filtro e listas.

## Riscos ativos

- Chave MAXADMIN em homologação: ver [[chave-api-por-usuario]].
- BMXAA10147E: voltou em 2026-10-29 com usuário em PT e sumiu com EN (2ª vez).
  Usuário da chave precisa estar em EN; afeta a chave por gerente. Ver
  [[chave-api-por-usuario]] e [[mas-mcp-server]].
- **MCP Server loga a `apikey` em texto puro (INFO).** Chave MAXADMIN de
  homologação exposta em 2026-10-29. Nova chave no `.env`; usuário **decidiu não
  revogar** a antiga (risco aceito: escrita total em homologação para quem lê os
  logs do pod). Mitigação necessária antes de chave de gerente. Ver
  [[mas-mcp-server]].
- Confirmado em runtime (2026-10-29): `SqlFormat.setTimestamp`, identidade do
  chamador via MCP, paginação com `getMbo(i)` (página 2). Não testado: páginas
  profundas (ex.: 700+) e desempenho.
