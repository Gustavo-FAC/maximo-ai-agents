---
title: Automation scripts como ferramentas
type: concept
sources: []
related: [[mas-mcp-server]], [[itambe-cimentos]], [[allowlist-somente-leitura]]
created: 2026-10-21
updated: 2026-10-21
---

# Automation scripts como ferramentas

Ferramentas de dados são automation scripts no Maximo, publicados no
[[mas-mcp-server]]. Fonte oficial em `maximo_scripts/`; nunca editar direto no Maximo.

## Regras

- Somente consulta. Nomes, descrições e parâmetros em inglês, com response schema.
- Parâmetros: intervalo de datas (obrigatório, com limite), campo de data, site,
  lista de wonum (com limite), status, prioridade, ativo, local, equipe, tipo de
  trabalho, paginação com total de registros, seleção de campos.

## Estado (2026-10-21)

- Nenhum script criado ainda.
- Primeiro candidato: consulta genérica de OS. Não depende do guia da
  [[itambe-cimentos]]; o guia só acrescenta filtros e campos.

## Perguntas abertas (precisam da doc do MCP Server)

- Como o script é registrado como ferramenta (nome, descrição)?
- Como recebe parâmetros e devolve resposta?
- Linguagem: Jython ou JavaScript?
