---
title: Chave de API por usuário
type: concept
sources: []
related: [[allowlist-somente-leitura]], [[itambe-cimentos]], [[mas-mcp-server]]
created: 2026-10-21
updated: 2026-10-29
---

# Chave de API por usuário

Decisão de arquitetura: cada gerente tem chave própria criada no Maximo do cliente,
guardada em cofre e vinculada ao login. Consultas herdam as permissões do usuário.

## Exceção atual (homologação)

- `.env` usa chave da **MAXADMIN**, só para testes iniciais.
- MAXADMIN tem escrita total: leitura depende só da [[allowlist-somente-leitura]].
- **Trocar antes de:** uso por gerente real, evals com dados reais, qualquer demo
  ao cliente.
- 2026-10-29: chave MAXADMIN apareceu em texto puro no log do pod do MCP. Nova
  chave gerada; a antiga **não foi revogada** por decisão do usuário (risco aceito).

## Observação: idioma do usuário (2026-10-29)

O MCP Server recusou ferramenta customizada com BMXAA10147E porque o usuário da
chave está em PT (detalhes em [[mas-mcp-server]]). Se isso se confirmar como regra
do produto, a chave por gerente implicaria usuário em inglês no Maximo, mudando a
interface do dia a dia do gerente. Não é decisão nem pré-requisito: falta confirmar
a causa e se o idioma pode ser informado por requisição.
