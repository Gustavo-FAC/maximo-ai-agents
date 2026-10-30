---
title: Itambé Cimentos
type: entity
sources: []
related: [[mas-mcp-server]], [[chave-api-por-usuario]], [[automation-scripts-como-ferramentas]]
created: 2026-10-21
updated: 2026-10-30
---

# Itambé Cimentos

Cliente piloto da plataforma. Tenant `itambe` (`TENANT_ID` no `.env`).

- Ambiente de **homologação** MAS 9.2 com [[mas-mcp-server]] ativo e validado (Fase 0).
- Conexão testada em 2026-10-21: OK.
- **Chave de teste é da MAXADMIN** (temporária, só para testes iniciais). Ver
  [[chave-api-por-usuario]] sobre o risco e a troca.
- Guia de levantamento da Fase 1 em preenchimento pelo consultor funcional. Quando
  voltar: colocar em `memoria/raw/`, fazer ingest e especificar os
  [[automation-scripts-como-ferramentas]].

## Dados (homologação, 2026-10-30)

- **Não usa classe de falha** (consultor funcional): sem FAILUREREPORT útil;
  `QUERYFAILUREREPORTS` cancelado ([[ferramentas-maximo]]).
- 18337 OS com `reportdate` de 2025-11-01 a 2026-10-30; 14709 ativos.
- Tipo de trabalho: corretiva = `CO`, preventiva = `MP` (a confirmar). Nas 92 OS
  com "vazamento" no período: 56 `CO`, 2 `MP`, 34 sem tipo.
- Muitas OS vêm de checklist de inspeção (descrição "NÃO CONFORME: <pergunta>").
- Descrições em maiúsculas, em geral sem acento ("OLEO").
- Perguntas ao consultor: significado dos tipos de trabalho; por que OS sem tipo;
  como separar OS de checklist das de falha.
