---
title: Ferramentas de dados (automation scripts) – plano
type: synthesis
sources: []
related: [[automation-scripts-como-ferramentas]], [[allowlist-somente-leitura]], [[estado-do-projeto]], [[itambe-cimentos]]
created: 2026-10-29
updated: 2026-10-29
---

# Ferramentas de dados – plano

Origem: tabela "Fase 2 – Ordem de construção e ferramentas" (18 nomes propostos em
português, por agente). Análise de 2026-10-29: cada nome é de um de três tipos.

- **Dados** → automation script no Maximo (este plano).
- **Cálculo** (inconsistências, tendências, risco, RPN, backlog por idade) →
  `analysis/` em Python (a IA não faz contas). Fora deste plano.
- **Texto** (resumir histórico, recomendar mitigações, propor programação) → o
  próprio LLM, sem ferramenta. "Propor programação" só sugere; nunca grava.

Decisão do usuário (2026-10-29): focar primeiro nas ferramentas feitas por script.

## Scripts

| # | Script | Tabelas | Cobre (nomes da tabela) | Fase | Estado |
|---|---|---|---|---|---|
| 1 | `QUERYASSETS` | ASSET, ASSETANCESTOR | buscar_ativos, histórico do ativo (cadastro) | P0 | escrito, não instalado |
| 2 | `QUERYFAILUREREPORTS` | FAILUREREPORT + WORKORDER | consultar_falhas, consultar_falhas_por_ativo | P0 | a fazer |
| 3 | `QUERYWORKORDERS` + `text` | WORKORDER | consultar_os, histórico de OS, buscar_os_similares, consultar_backlog | P0 | funcionando; `text` a fazer |
| 4 | histórico de status (opção) | WOSTATUS, ASSETSTATUS, ASSETTRANS | histórico de uma OS / paradas e movimentações do ativo | P0 | a definir |
| 5 | `QUERYJOBPLANS` | JOBPLAN, JOBTASK | consultar_procedimentos | P1 | a fazer |
| 6 | `QUERYWOMATERIALS` | WPMATERIAL, INVBALANCES | verificar_materiais | P2 | a fazer |
| 7 | `QUERYMETERREADINGS` | METERREADING, MEASUREMENT | consultar_medicoes | P3 | a fazer |

Ordem combinada: 1 → 2 → 3. `buscar_documentos` (conteúdo de anexos) não vira script:
exige RAG e guardar documento do cliente (decisão de arquitetura, adiada).

## Decisões

- **"consultar_historico"** (usuário, 2026-10-29): vale para OS e ativos, um ou
  vários. Não é ferramenta própria: a IA combina `QUERYWORKORDERS` (OS do ativo ou
  por wonum) e `QUERYASSETS` (cadastro/situação) conforme o prompt. Lacuna: mudanças
  de status (WOSTATUS) e paradas/movimentações (ASSETSTATUS/ASSETTRANS); proposta é
  opção ligada sob pedido nas duas ferramentas, depois de conferir colunas
  (`apischema` com subesquema deu HTTP 500).
- **Bloco comum copiado** (usuário, 2026-10-29, opção "a"): sem script biblioteca.
  Trecho entre `# --- BEGIN COMMON` e `# --- END COMMON ---` igual em todos;
  `tests/unit/test_script_common.py` confere. `QUERYWORKORDERS` recebe o bloco no
  passo 3.
- **`QUERYASSETS` sem data obrigatória:** ativo é cadastro; `page_size` limita e
  `total` é exato. Exceção à regra "intervalo de datas obrigatório" **confirmada
  pelo usuário** (2026-10-29): datas obrigatórias só em consultas de movimento;
  `CLAUDE.md` atualizado.
- **Só atributos padrão** nos scripts. Itambé tem matriz de criticidade própria no
  ASSET (`cci_critic`, `cci_pontos`, `cci_prod`, `cci_custo`, `cci_qual`, `cci_ssma`,
  `cci_clas`, `cci_calif`, `cci_dt_crit`, visto no `apischema` MXAPIASSET). Útil para
  risco/FMEA; entra como extensão por cliente quando o guia explicar os campos.
- **Busca por texto:** cada palavra vira `upper(description) like :n` com `%palavra%`
  no bind; `%` e `_` recusados (escape muda entre bancos). Sem busca por semelhança
  (embeddings exigiriam guardar dados do cliente).
