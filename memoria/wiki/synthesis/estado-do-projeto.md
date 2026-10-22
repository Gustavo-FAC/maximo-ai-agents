---
title: Estado do projeto
type: synthesis
sources: []
related: [[mas-mcp-server]], [[allowlist-somente-leitura]], [[automation-scripts-como-ferramentas]], [[chave-api-por-usuario]]
created: 2026-10-21
updated: 2026-10-22
---

# Estado do projeto

Ler no início de cada sessão. Atualizar no fim.

## Feito

- Esqueleto do repo (estrutura, `pyproject.toml`, settings, pre-commit, teste).
- Fase 0: MAS 9.2 com MCP Server validado.
- 2026-10-21: `.gitignore` revisado; `uv sync`; hook pre-commit instalado; testes e
  Ruff OK.
- 2026-10-21: `check_connection` corrigido (SDK mcp 2.3, UTF-8, mostra descrição e
  parâmetros) e executado contra homologação Itambé: conexão OK, 1 ferramenta
  (`apischema`).
- 2026-10-21: memória do projeto criada em `memoria/` (este wiki).
- 2026-10-22: ingest das docs do MCP Server e de Automation Scripts.
- 2026-10-22: script `QUERYWORKORDERS` + 19 testes unitários (não instalado).

## Git

Commit inicial feito em 2026-10-21 na branch `chore/esqueleto-inicial` (sem push).

## Próximo

1. ~~Ingest das docs~~ feito em 2026-10-22: ver [[doc-mcp-server]], [[guia-automation-scripts]].
2. ~~Escrever primeiro automation script~~ feito em 2026-10-22: `QUERYWORKORDERS`.
   1ª instalação (2026-10-22) com problemas vistos no OAS: ver
   [[automation-scripts-como-ferramentas]]. Próximo: reinstalar seguindo
   `maximo_scripts/queryworkorders/INSTALACAO.md` e rodar o checklist.
3. Em paralelo, sem depender do Maximo: gateway de LLM em `llm/` com Ollama (passo 5)
   e agente de teste com `apischema` (passo 6).
4. Implementar [[allowlist-somente-leitura]] (passo 4).

## Riscos ativos

- Chave MAXADMIN em homologação: ver [[chave-api-por-usuario]].
- 1ª versão do `QUERYWORKORDERS` no Maximo expõe `authapp`/`authsigoption` como
  parâmetros: manter **inativa** até a reinstalação.
