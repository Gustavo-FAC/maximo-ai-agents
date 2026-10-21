---
title: Chave de API por usuário
type: concept
sources: []
related: [[allowlist-somente-leitura]], [[itambe-cimentos]]
created: 2026-10-21
updated: 2026-10-21
---

# Chave de API por usuário

Decisão de arquitetura: cada gerente tem chave própria criada no Maximo do cliente,
guardada em cofre e vinculada ao login. Consultas herdam as permissões do usuário.

## Exceção atual (homologação)

- `.env` usa chave da **MAXADMIN**, só para testes iniciais.
- MAXADMIN tem escrita total: leitura depende só da [[allowlist-somente-leitura]].
- **Trocar antes de:** uso por gerente real, evals com dados reais, qualquer demo
  ao cliente.
