---
title: Itambé Cimentos
type: entity
sources: []
related: [[mas-mcp-server]], [[chave-api-por-usuario]], [[automation-scripts-como-ferramentas]]
created: 2026-10-21
updated: 2026-11-04
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

- **Planos de trabalho** (2026-11-03): 2102, 2025 ativos; status gravado em
  português (sinônimo **ATIVO** de ACTIVE); `templatetype` MANUTENÇÃO; 203 planos
  sem site e sem org (nível sistema); site principal `FABRICA`, org `ITAMBE`.
  `persongroup` vazio nos planos vistos. Descrição longa em ~metade, muitas vezes
  só um código (ex.: `PS1486`, talvez procedimento de segurança: perguntar).
  **Plano ligado à location, não ao ativo** (2026-11-04): `L3T05M1` tem 8 planos;
  os 3 ativos dela (ACI0343, MCA5853, PEL0151) não têm ligação direta.
- **Não usa classe de falha** (consultor funcional): sem FAILUREREPORT útil;
  `QUERYFAILUREREPORTS` cancelado ([[ferramentas-maximo]]).
- 18337 OS com `reportdate` de 2025-11-01 a 2026-10-30; 14709 ativos.
- Tipo de trabalho: corretiva = `CO`, preventiva = `MP` (a confirmar). Nas 92 OS
  com "vazamento" no período: 56 `CO`, 2 `MP`, 34 sem tipo.
- Muitas OS vêm de checklist de inspeção (descrição "NÃO CONFORME: <pergunta>").
- Descrições em maiúsculas, em geral sem acento ("OLEO").
- Perguntas ao consultor: significado dos tipos de trabalho; por que OS sem tipo;
  como separar OS de checklist das de falha.

## Paradas de ativo (2026-11-04)

- Homologação quase não usa ASSETSTATUS: ~120 linhas no total, 4 em 2025, 0 em 2026,
  site `FABRICA`, código de parada `PCE` na maioria.
- `downtime` gravado nem sempre é a diferença entre queda e retorno (MCC2213: 08:00 →
  10:56, `downtime` 2.0). ACI1020 tem 5 pares idênticos (mesma OS 979093).
- A confirmar com o consultor: se produção registra paradas no Maximo.

## Materiais (2026-11-04)

- **Itambé não planeja material no Maximo** (usuário, 2026-11-04): WPMATERIAL vazio,
  planejamento fica fora (Protheus). Campos próprios no WPMATERIAL (`sanum` =
  solicitação do Protheus, `justificativa`, `prioridade`, `wpm1` a `wpm6`) existem,
  mas sem uso. Material na Itambé = só consumo (`QUERYMATUSAGE`).
- Baixas (MATUSETRANS): 5241 em nov/25–nov/26 (5011 baixas, 230 devoluções); dados até
  jun/2026. Site `FABRICA`, almoxarifados `FAB`, `30`. OS 1116802 = material de limpeza
  recorrente (109 baixas). `issuetype` em PT (`EMISSÃO`, `RETORNAR`); `issueid` vazio
  nas devoluções.
