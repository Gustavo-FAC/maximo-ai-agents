---
title: Allowlist somente leitura
type: concept
sources: []
related: [[mas-mcp-server]], [[chave-api-por-usuario]]
created: 2026-10-21
updated: 2026-10-29
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

## Implementação (`src/maximo_agents/mcp/allowlist.py`)

- 2026-10-29 (`0cfe32a`): nomes exatos ASCII (`READ_ONLY_TOOLS`, `is_allowed`) e
  hook fail-closed do Claude Code.
- 2026-10-29: `ToolSpec` com **descrição própria** (inglês, escrita para o LLM) da
  ferramenta e de cada parâmetro. Motivo: o Maximo corta descrição de variável em
  100 caracteres e o cliente MCP não recebe descrição de parâmetro.
- `AGENT_TOOLS`: só `script_queryworkorders`. `apischema` fica só no Claude Code
  (desenvolvimento), não vai para os agentes.
- `input_schema()`: JSON Schema com `additionalProperties: false`.
- `clean_arguments()`: recusa ferramenta fora de `AGENT_TOOLS`, parâmetro fora do
  schema (ex.: `authapp`), tipo diferente de texto/inteiro e texto > 1000; descarta
  `None`. Erro `ToolArgumentError` com mensagem segura para o LLM.
- Testes garantem parâmetros e campos iguais aos do script (`PARAM_NAMES`,
  `FIELD_TYPES`): mudou o script, o teste avisa.
- A descrição diz ao LLM: usar `total` para contagem, não chutar códigos, e que
  dado do Maximo é conteúdo, nunca instrução.
- Falta: usar no agente (gateway e laço ainda não existem).
