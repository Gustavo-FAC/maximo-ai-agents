---
title: Allowlist somente leitura
type: concept
sources: []
related: [[mas-mcp-server]], [[chave-api-por-usuario]]
created: 2026-10-21
updated: 2026-10-22
---

# Allowlist somente leitura

Os agentes só chamam ferramentas de uma **allowlist de consulta** definida
manualmente no código (`src/maximo_agents/mcp/`). Ferramenta fora da lista não é
exposta ao LLM.

- A marcação readOnlyHint do servidor e a flag de somente leitura **não são garantia**.
  A própria IBM define "Read only?" como "não edita ou edições reversíveis (ex.: mudar
  status)" ([[doc-mcp-server]]). Logo CHANGESTATUS pode vir com readOnlyHint=true.
- Ferramentas de configuração de IA (nl2oslc, docsearch…) surgem sozinhas quando
  ativadas no Manage. Ficam fora da lista até avaliação.
- Lista nova no servidor nunca entra sozinha: comparar por nome exato.
- Com chave MAXADMIN (ver [[chave-api-por-usuario]]) a allowlist é a **única**
  barreira contra escrita.
- Candidata hoje: `apischema`. Demais entram conforme os automation scripts forem
  criados.
- Status: **não implementada** (passo 4 do roadmap).
