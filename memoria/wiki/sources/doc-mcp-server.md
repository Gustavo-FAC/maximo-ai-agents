---
title: Doc do Maximo MCP Server (resumo IBM, out/2026)
type: source
sources: [docs/Maximo MCP Server — Documentação.docx]
related: [[mas-mcp-server]], [[automation-scripts-como-ferramentas]], [[allowlist-somente-leitura]], [[chave-api-por-usuario]]
created: 2026-10-22
updated: 2026-10-22
---

# Doc do Maximo MCP Server

Resumo em português das páginas IBM (set–out/2026), feito pelo Gustavo em 2026-10-20.
Arquivo em `docs/` (versionado).

## Pontos-chave

- Pod no OpenShift. **Manage é a fonte da verdade** da lista de ferramentas; o pod
  faz polling a cada `POLLING_FREQUENCY` (padrão 10 min). Reiniciar o pod força
  refresh (interrompe chamadas).
- Cada `tools/call` vira um **POST REST** no Manage. `TOOL_RESPONSE_TIMEOUT` padrão
  10 min.
- Origens de ferramenta: configuração de IA (mcc, pcc, similarity, nl2oslc,
  docsearch, insightsgenerator; tabela `MAXAICFGTOOL`), object structure, automation
  script, workflow, API route.
- Ferramentas padrão de object structure: CHANGESTATUS, CREATEFOLLOWUPWORKORDER,
  ENTERMETERREADING, MOVEASSET, CHANGELOCATION, REPORTDOWNTIME, CREATESR (todas
  escrita).

## Automation script como ferramenta

1. Automation Script → Create → Script (sem launch point), nome único.
2. Descrição em inglês (é o que o agente usa para escolher).
3. Response Schema opcional, **recomendado** (sem ele não encadeia).
4. Active?; **uma variável por parâmetro de entrada, binding Literal**. Variável
   `href` vira o `mbo` implícito.
5. More Actions → **Add/Modify MCP Tool**: título, notas de processamento, flags.
6. Resposta: `responseBody = OslcUtils.jsonToBytes(jo)`. Usa o framework de
   scripted API routes.

## Flags (atenção)

- **Read only?** = "não edita **ou edições reversíveis (ex.: mudar status)**".
  Confirma que a flag não indica somente leitura. Ver [[allowlist-somente-leitura]].
- Destructive hint? = assistente pede aprovação.
- Query API as a response? = saída no formato padrão de query.

## Autenticação

| Cenário | Header |
|---|---|
| Integração / conta de serviço | `apikey` |
| Multiusuário | `x-access-token` (JWT do usuário) |

Nossa decisão (chave por usuário via `apikey`) cabe no primeiro modo. Ver
[[chave-api-por-usuario]].

## Utilidades para depurar

- `GET /oslc/listmcptools` ou `/api/listmcptools`: lista simplificada
  (total, path, method, name, description, type, title).
- `GET /api/oas?aitools=1`: confere se a ferramenta pode ser carregada no MCP.
- MCP Inspector: Streamable HTTP, Connection Type = Proxy.
