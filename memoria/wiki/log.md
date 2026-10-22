# Log

## [2026-10-21] setup | Revisão do .gitignore e ambiente
`uv sync`, hook pre-commit instalado, testes e Ruff OK. Pasta vazia aninhada
`maximo-ai-agents/` removida.

## [2026-10-21] test | Conexão com MCP Server da Itambé
`check_connection` corrigido para SDK mcp 2.3 (`read_only_hint`) e UTF-8. Conexão OK,
1 ferramenta: `apischema`. Usuário confirmou: chave MAXADMIN para teste, scripts
ainda não criados. Páginas: [[mas-mcp-server]], [[itambe-cimentos]].

## [2026-10-21] setup | Memória do projeto no padrão Memoriki
Criado `memoria/` com esquema, índice, log, 2 entidades, 3 conceitos e
[[estado-do-projeto]]. MemPalace configurado (`mempalace.yaml`), não instalado.

## [2026-10-21] setup | Commit inicial
Doc do MCP Server adicionada em `docs/` pelo usuário (verificada: sem segredos, só URLs
de exemplo). Commit inicial na branch `chore/esqueleto-inicial`, sem push. Ingest da
doc fica para a próxima sessão.

## [2026-10-22] ingest | Doc do MCP Server e guia de Automation Scripts
Lidos `docs/Maximo MCP Server — Documentação.docx` e
`docs/Automation_Scripts_IBM_Maximo.docx` (novo, não versionado). Criadas
[[doc-mcp-server]] e [[guia-automation-scripts]]. Respondidas as perguntas de
[[automation-scripts-como-ferramentas]] (registro, parâmetros literais, Jython) e
abertas 4 novas para testar no primeiro script. [[allowlist-somente-leitura]]:
IBM define "Read only?" incluindo edições reversíveis.
