---
title: Estado do projeto
type: synthesis
sources: []
related: [[mas-mcp-server]], [[allowlist-somente-leitura]], [[automation-scripts-como-ferramentas]], [[chave-api-por-usuario]], [[doc-mcp-server]], [[guia-automation-scripts]]
created: 2026-10-21
updated: 2026-10-29
---

# Estado do projeto

Ler no início de cada sessão. Atualizar no fim.

## Onde paramos (2026-10-29, fim)

**`QUERYWORKORDERS` funcionando via MCP** em homologação (Claude Code → MCP Server
→ script): dados reais, paginação, filtros e validações conferidos. Correções que
levaram até aqui: sem `datetime`, `SqlFormat(user_info, ...)`, lógica em `_main`
(sem `globals()` em variável de topo), sem `isLoggingEnabled`. 44 testes.
**Mudanças ainda não commitadas.** Detalhes em [[automation-scripts-como-ferramentas]].
Próximo: commit; depois item 2 de "Falta".

## Histórico do dia (2026-10-29)

`QUERYWORKORDERS` reinstalado em homologação. OAS confere com o repositório (14
parâmetros, 12 chaves de resposta, sem `u200b`, sem `authapp`/`authsigoption`).
Claude Code conectado ao MCP (`.mcp.json`, guard da allowlist, commit `0cfe32a`)
enxerga `script_queryworkorders` após `/mcp` reconectar.

1ª chamada voltou com BMXAA10147E (idioma PT do usuário da chave). Registrado como
**observação**, não pré-requisito: ver [[mas-mcp-server]] e
[[chave-api-por-usuario]]. Usuário trocado para EN → script passou a rodar e falhou
em `No module named datetime` (Jython do Maximo sem biblioteca padrão). Corrigido
(classe `Day`) e reinstalado: sem erro, mas resposta MCP toda `null` (MCP não
recebe nosso JSON). 2ª correção no repo (detecção do runtime, `userInfo` como
reserva, `OslcUtils.jsonToBytes`, log das variáveis implícitas), 43 testes,
**ainda não commitada**. Erro seguinte (HTTP 500 BMXAA1649E): log do Manage mostrou
`StackOverflowError` em `copyFromBindings` porque `_scope = globals()` ficava no
topo do script. Corrigido no repo (lógica em `_main`, 44 testes); `SqlFormat` com
`UserInfo` também mantido. Detalhes em [[automation-scripts-como-ferramentas]].
Próximo: colar o código novo, repetir o passo 7 do `INSTALACAO.md` (Claude Code
testa via `script_queryworkorders`) e pegar a linha de log `implicit vars`; se
funcionar, commitar.

## Onde paramos antes (2026-10-22)

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
- 2026-10-29: Claude Code ligado ao MCP do Maximo: `.mcp.json` (URL e chave por
  variável de ambiente), `scripts/claude-maximo.ps1`, `mcp/allowlist.py` (nomes
  exatos ASCII) e hook `mcp/claude_code_guard.py` (fail-closed); settings negam as
  7 ferramentas padrão de escrita. 12 testes. Commit `0cfe32a`.
- 2026-10-29: `QUERYWORKORDERS` reinstalado; OAS validado; execução bloqueada por
  BMXAA10147E (observação em [[mas-mcp-server]]).

## Git

Branch `chore/esqueleto-inicial`, 5 commits, **sem push**.

## Falta (ordem sugerida)

1. ~~Testar execução do `QUERYWORKORDERS`~~ Feito 2026-10-29. Falta só a linha
   DEBUG `implicit vars` (origem dos parâmetros e da identidade).
2. Completar [[allowlist-somente-leitura]] para o agente: nomes exatos já feitos
   (`0cfe32a`); falta descrição própria e rica de cada ferramenta (o cliente MCP
   não recebe descrição de parâmetro) e nunca repassar parâmetros fora do schema
   nosso.
3. Gateway de LLM em `llm/` com Ollama (não depende do Maximo; pode ir em paralelo).
4. Primeiro agente: laço com `QUERYWORKORDERS`, limite de 5 voltas.
5. Pequeno CLI `call_tool` para testar ferramentas sem MCP Inspector (opcional).
6. Quando o guia da Itambé voltar: novos scripts/filtros/campos e `tests/evals/`.
7. Trocar a chave MAXADMIN por chave de gerente e testar com usuário **sem** acesso
   a um site (checklist do README do script).

## Riscos ativos

- Chave MAXADMIN em homologação: ver [[chave-api-por-usuario]].
- BMXAA10147E: se exigir usuário em EN, afeta a chave por gerente (observação, a
  confirmar). Ver [[chave-api-por-usuario]].
- **MCP Server loga a `apikey` em texto puro (INFO).** Chave MAXADMIN de
  homologação exposta em 2026-10-29. Nova chave no `.env`; usuário **decidiu não
  revogar** a antiga (risco aceito: escrita total em homologação para quem lê os
  logs do pod). Mitigação necessária antes de chave de gerente. Ver
  [[mas-mcp-server]].
- Confirmado: Jython do Maximo **sem** `datetime` (sem biblioteca padrão); corrigido.
- Confirmado em runtime (2026-10-29): `SqlFormat.setTimestamp`, identidade do
  chamador via MCP, paginação com `getMbo(i)` (página 2). Não testado: páginas
  profundas (ex.: 700+) e desempenho.
