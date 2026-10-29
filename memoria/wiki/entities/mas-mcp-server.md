---
title: MCP Server do MAS 9.2
type: entity
sources: []
related: [[allowlist-somente-leitura]], [[automation-scripts-como-ferramentas]], [[itambe-cimentos]]
created: 2026-10-21
updated: 2026-10-29
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

Em 2026-10-29, após reinstalar o `QUERYWORKORDERS`:

| Ferramenta | readOnlyHint | toolType | Descrição |
|---|---|---|---|
| `apischema` | true | APIROUTE | idem acima |
| `script_queryworkorders` | true | AUTOSCRIPT (`custom: true`) | Read-only work order search: date range (YYYY-MM-DD), filters, paging, total count. |

Nenhuma ferramenta de escrita exposta. Ver [[automation-scripts-como-ferramentas]].

## Observação: idioma do usuário (BMXAA10147E), 2026-10-29

Chamada a `script_queryworkorders` pelo Claude Code (MCP) falhou antes de executar o
script, com e sem parâmetros válidos:

```
HTTP 400: BMXAA10147E - O código de idioma do usuário PT é inválido para inferência.
Assim, considere modificar para um usuário com base em inglês
```

- A URL interna da chamada termina em `/maximo/api/script_queryworkorders?ccm=1`.
- Com o mesmo usuário e a mesma chave, `apischema` funcionou. A checagem parece
  valer só para ferramentas customizadas (AUTOSCRIPT), não para APIROUTE.
- Usuário da chave em homologação está com idioma PT.
- **Não confirmado:** se é regra fixa do produto, configuração do MCP Server ou do
  serviço de IA do MAS, e se há como informar o idioma por requisição.
- Impacto possível na arquitetura: ver [[chave-api-por-usuario]].
- Teste no mesmo dia: usuário de homologação trocado para EN → o erro sumiu e o
  script passou a executar (mensagens do Maximo vieram em inglês). A troca de
  idioma resolve; segue em aberto se há alternativa sem mudar o usuário.

## Risco: MCP Server grava a `apikey` em log, 2026-10-29

O pod do MCP Server loga em **INFO** os headers de cada chamada, com a `apikey`
completa em texto puro (`Extracted headers from HTTP request` e `Sending POST call
... with headers`). Visto no log de homologação Itambé. A chave MAXADMIN de
homologação vazou assim; o usuário gerou chave nova mas **decidiu não revogar a
antiga** (risco aceito, 2026-10-29).

- Choca com a regra "nunca registrar chaves em logs" e com a [[chave-api-por-usuario]]:
  toda chave de gerente ficaria no log do pod.
- Mitigar antes de qualquer chave real: nível de log do pod acima de INFO e/ou
  correção da IBM; restringir acesso aos logs do pod. **Não decidido.**
- Ao pedir log do MCP ao usuário: pedir para apagar `apikey` antes de colar.

## Confirmado no log do MCP, 2026-10-29

- `tools/call` vira `POST /maximo/api/script_<nome>?ccm=1` com os argumentos como
  **corpo JSON** (`Content-Type: application/json`), não query string.
- HTTP 200 do Manage aparece como `completed successfully` mesmo quando a resposta
  mapeada vem toda `null`.

## Observação: descrições de parâmetros no cliente MCP, 2026-10-29

No Claude Code, o esquema de `script_queryworkorders` chegou só com nome e tipo
(`string | null`) de cada parâmetro, sem as descrições do OAS. O modelo não vê
limites nem formatos ("max 366 days", "YYYY-MM-DD"). Reforça a regra da
[[allowlist-somente-leitura]] de guardar descrição própria de cada ferramenta.

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
