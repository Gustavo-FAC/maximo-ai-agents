---
title: MCP Server do MAS 9.2
type: entity
sources: []
related: [[allowlist-somente-leitura]], [[automation-scripts-como-ferramentas]], [[itambe-cimentos]]
created: 2026-10-21
updated: 2026-10-22
---

# MCP Server do MAS 9.2

Servidor MCP oficial do Maximo Application Suite. Única via de acesso ao Maximo.

- Rota pública no OpenShift; transporte **Streamable HTTP**; autenticação por header
  `apikey`.
- Variáveis: `MAXIMO_MCP_URL`, `MAXIMO_API_KEY`.
- Teste: `uv run python -m maximo_agents.mcp.check_connection`.

## Ferramentas expostas (homologação Itambé, 2026-10-21)

| Ferramenta | readOnlyHint | Parâmetros | Descrição |
|---|---|---|---|
| `apischema` | true | `api`, `nested` | Esquema JSON de uma API do Maximo (estrutura de objeto) |

Só uma ferramenta porque os automation scripts ainda não foram criados (esperado).

Ferramentas padrão de escrita que **nunca** entram na allowlist: CHANGESTATUS,
CREATEFOLLOWUPWORKORDER, ENTERMETERREADING, MOVEASSET, CHANGELOCATION, REPORTDOWNTIME,
CREATESR. Ver [[allowlist-somente-leitura]].

## Notas do SDK Python (mcp 2.3.0)

- Campos em snake_case: `ToolAnnotations.read_only_hint`, `Tool.input_schema`
  (na 1.x eram `readOnlyHint` e `inputSchema`).
- Cliente: `create_mcp_http_client(headers=...)` mais
  `streamable_http_client(url, http_client=...)`.
- Console do Windows: forçar `sys.stdout.reconfigure(encoding="utf-8")` para acentos.

## Documentação

Resumo em [[doc-mcp-server]] (ingest 2026-10-22). Destaques: polling de 10 min,
timeout de 10 min, auth `apikey` ou `x-access-token` (JWT), endpoints de depuração
`/api/listmcptools` e `/api/oas?aitools=1`.
