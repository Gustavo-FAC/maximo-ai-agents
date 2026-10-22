---
title: Automation scripts como ferramentas
type: concept
sources: [docs/Maximo MCP Server — Documentação.docx, docs/Automation_Scripts_IBM_Maximo.docx]
related: [[mas-mcp-server]], [[itambe-cimentos]], [[allowlist-somente-leitura]], [[doc-mcp-server]], [[guia-automation-scripts]]
created: 2026-10-21
updated: 2026-10-22
---

# Automation scripts como ferramentas

Ferramentas de dados são automation scripts no Maximo, publicados no
[[mas-mcp-server]]. Fonte oficial em `maximo_scripts/`; nunca editar direto no Maximo.

## Regras

- Somente consulta. Nomes, descrições e parâmetros em inglês, com response schema.
- Parâmetros: intervalo de datas (obrigatório, com limite), campo de data, site,
  lista de wonum (com limite), status, prioridade, ativo, local, equipe, tipo de
  trabalho, paginação com total de registros, seleção de campos.

## Respostas (2026-10-22, de [[doc-mcp-server]] e [[guia-automation-scripts]])

- **Registro:** script sem launch point → descrição em inglês → response schema →
  Active? → More Actions > Add/Modify MCP Tool (título, notas, flags). Aparece no
  próximo polling (10 min).
- **Parâmetros:** uma variável por parâmetro, binding Literal, tipo em
  `literaldatatype` (ALN, INTEGER, DATETIME…). Listas (wonum, status) vão como ALN
  separado por vírgula e o script divide.
- **Resposta:** JSON via `responseBody = OslcUtils.jsonToBytes(jo)`.
- **Linguagem:** Jython (exemplos IBM em Jython). JS/Nashorn também funciona.

## Regras de implementação (derivadas)

- Consulta com `MXServer.getMboSet("WORKORDER", userInfo)` do usuário da chamada
  → herda segurança de site/dados do Maximo.
- Filtros só via `SqlFormat.setObject` (nunca concatenar valor no where).
- `count()` uma vez para o total; `cleanup()` em `finally`.
- Validar limites no script: intervalo de datas máximo, tamanho da lista de wonum,
  `page_size` máximo. O agente não é confiável para respeitar limites.
- Declarar `authapp` / `authsigoption` (ex.: WOTRACK + READ) para exigir permissão
  de leitura de OS.
- Flag **Read only?** marcada, mas sem confiar nela (ver
  [[allowlist-somente-leitura]]).

## Perguntas abertas (testar no primeiro script)

- Parâmetro opcional: o schema gerado pelo MCP marca todas as variáveis como
  obrigatórias? Como passar "vazio"?
- Como DATETIME chega pelo MCP (formato ISO aceito?).
- `userInfo` disponível no script chamado via MCP: `request.getUserInfo()` existe
  nesse caminho? É o dono da `apikey`?
- `authapp`/`authsigoption` também valem no caminho MCP?

## Estado

- Nenhum script criado ainda. Primeiro: consulta genérica de OS.
