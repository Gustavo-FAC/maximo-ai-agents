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

## [2026-10-22] code | Primeiro automation script: QUERYWORKORDERS
Escrito em Jython 2.7 (pedido do usuário: scripts em Python) em
`maximo_scripts/queryworkorders/` com response schema e README (descrição da
ferramenta, variáveis, registro, checklist de validação). Lógica pura testada em
CPython (19 testes). Ruff: ignores `UP`, `B904`, `S608` para `maximo_scripts/**`.
Não instalado no Maximo. Páginas: [[automation-scripts-como-ferramentas]],
[[estado-do-projeto]].

## [2026-10-22] docs | Guia de instalação do QUERYWORKORDERS
`maximo_scripts/queryworkorders/INSTALACAO.md`: passo a passo campo a campo
(wizard, 16 variáveis literais, response schema, Add/Modify MCP Tool, validação).
Script passou a ler parâmetros de variável literal, `requestBody` JSON ou query
string (canal do MCP ainda não confirmado) e loga a origem. 21 testes.

## [2026-10-22] test | 1ª instalação do QUERYWORKORDERS (OAS)
Usuário criou o script e enviou `/api/oas?aitools=1`. Ferramenta registrada
(`/script_queryworkorders`, readOnlyHint true), mas: U+200B no nome e em 13
variáveis (colagem); `authapp`/`authsigoption` expostos como parâmetros; descrições
cortadas em 100. Correção: permissão WOTRACK/READ checada no código
(APPLICATIONAUTH), variáveis de segurança removidas, `changedate` fora de
`date_field`, guia reescrito (remover e recriar, digitar nomes). 22 testes.
Script atual no Maximo deve ficar inativo até reinstalar.

## [2026-10-22] session | Fim de sessão
Feito: ingest das docs, `QUERYWORKORDERS` (script, schema, README, guia, 22 testes),
1ª instalação avaliada pelo OAS e corrigida. Commits `48a1eed`, `d5998cf` (sem push).
Parado em: usuário vai reinstalar o script e enviar OAS, `check_connection` e
respostas de teste. [[estado-do-projeto]] reescrito com "Onde paramos" e "Falta".

## [2026-10-29] code | Claude Code ligado ao MCP do Maximo
`.mcp.json` com URL e chave por variável de ambiente, `scripts/claude-maximo.ps1`,
allowlist de nomes exatos e hook fail-closed `claude_code_guard.py`; settings negam
as 7 ferramentas padrão de escrita. 12 testes. Commit `0cfe32a`. Registrado agora
(faltava no log).

## [2026-10-29] test | QUERYWORKORDERS reinstalado: OAS ok, execução bloqueada
OAS conferido contra o repositório (14 parâmetros, 12 chaves de resposta, sem
`u200b`, sem variáveis de segurança). Só `apischema` e `script_queryworkorders`
expostos, ambos readOnlyHint. Chamada via Claude Code voltou com BMXAA10147E
(idioma PT do usuário da chave) antes de executar o script; `apischema` funcionou
com a mesma chave. Registrado como **observação** (não pré-requisito) em
[[mas-mcp-server]], [[chave-api-por-usuario]], [[automation-scripts-como-ferramentas]]
e no `INSTALACAO.md`. Também observado: cliente MCP recebe parâmetros sem descrição.
[[estado-do-projeto]] atualizado.

## [2026-10-29] fix | Idioma EN resolveu BMXAA10147E; script sem datetime
Usuário de homologação trocado para EN: BMXAA10147E sumiu, script executou e falhou
em `ImportError: No module named datetime`. Jython do Maximo não tem biblioteca
padrão. `QUERYWORKORDERS.py`: `datetime` trocado por classe `Day` (Hinnant) e
`parse_iso_day`; testes novos (calendário 1900-2100 contra `datetime`, bissexto,
virada de ano, datas inválidas, guarda de imports). 43 testes, Ruff ok. Falta
reinstalar no Maximo. Páginas: [[mas-mcp-server]],
[[automation-scripts-como-ferramentas]], [[estado-do-projeto]].

## [2026-10-29] fix | Resposta MCP toda null
Script reinstalado sem `datetime` rodou sem erro, mas o MCP devolveu todas as chaves
do response schema em `null` (até no caso de erro). Hipóteses: `request` ausente no
caminho MCP (bloco principal não rodava) e/ou `responseBody` String em vez de
`OslcUtils.jsonToBytes`. Correção cobre as duas e loga variáveis implícitas
presentes. 43 testes. Falta reinstalar. [[automation-scripts-como-ferramentas]].

## [2026-10-29] test | Log do MCP: NPE e apikey em texto puro
Log do pod do MCP: versão com `OslcUtils.jsonToBytes` deu HTTP 500 BMXAA1649E
(NullPointerException) inclusive sem `date_to`. Confirmado que argumentos chegam
como corpo JSON. **Risco:** o pod loga a `apikey` completa em INFO; chave MAXADMIN
de homologação exposta, revogação pedida ao usuário. Páginas: [[mas-mcp-server]],
[[automation-scripts-como-ferramentas]], [[estado-do-projeto]]. Falta stack trace do
Manage.

## [2026-10-29] decision | Chave MAXADMIN antiga não revogada
Usuário gerou chave nova (no `.env`) e decidiu não revogar a antiga, exposta no
log do pod do MCP. Registrado como risco aceito em [[mas-mcp-server]],
[[chave-api-por-usuario]] e [[estado-do-projeto]].

## [2026-10-29] fix | NPE: SqlFormat sem UserInfo
Chave nova reconectada; `script_queryworkorders` ainda dá BMXAA1649E. Causa provável:
`SqlFormat(where)` sem `UserInfo` na checagem APPLICATIONAUTH (roda antes da
validação, por isso falha até sem `date_to`). Trocado por `SqlFormat(user_info, ...)`
e captura de `java.lang.Throwable`. 43 testes, Ruff ok. Falta reinstalar.
[[automation-scripts-como-ferramentas]].

## [2026-10-29] fix | BMXAA1649E: StackOverflowError por globals() no topo
Usuário reinstalou e colou o log do pod do Manage: script terminava; o erro vinha
depois, em `JSR223ScriptDriver.copyFromBindings`, que converte toda variável de topo
em texto. `_scope = globals()` recursava em `toString` → `StackOverflowError`. Lógica
movida para `_main(scope, throwable)`; teste `ast` impede `globals()` em variável de
topo. 44 testes, Ruff ok. Falta reinstalar. Log colado tinha IDs de usuários do
Maximo; não registrados. [[automation-scripts-como-ferramentas]],
[[estado-do-projeto]].

## [2026-10-29] fix | ScriptService sem isLoggingEnabled
Versão com `_main` reinstalada: HTTP 500 resolvido, MCP devolve nosso JSON. Ambas as
chamadas deram `internal_error`; log do Manage: `ScriptService` sem
`isLoggingEnabled` (recomendação errada do guia). Removido, `log_debug` direto.
44 testes. [[guia-automation-scripts]] corrigido. Falta reinstalar.

## [2026-10-29] test | QUERYWORKORDERS funcionando via MCP
Reinstalado. Claude Code chamou `script_queryworkorders`: jan/2026 total 3900,
paginação, filtros (status, worktype, wonums, siteid, date_field, fields) e erros de
validação (required, range_too_large, out_of_range) corretos. Perguntas abertas do
runtime respondidas em [[automation-scripts-como-ferramentas]]. Pendente: linha
`implicit vars` e teste com usuário sem acesso a site. [[estado-do-projeto]].

## [2026-10-29] decision | Datas opcionais com wonums
Teste "status das OS X e Y" exigiu inventar intervalo de datas; OS com mais de 366
dias ficaria inacessível. Usuário escolheu: com `wonums` (máx. 50) e sem as duas
datas, sem filtro de data. Uma data só continua `required`; lista vazia não libera.
`build_query`, README, `INSTALACAO.md` (descrições ≤100), response schema e
`CLAUDE.md` atualizados. 46 testes. Falta reinstalar. [[automation-scripts-como-ferramentas]].

## [2026-10-29] test | Datas opcionais com wonums validadas no Maximo
Reinstalado (código, Description, variáveis). Via MCP: 2 wonums sem datas → total 2,
datas `null`; sem parâmetros → `required`; wonum + só `date_from` → `required`
(`date_to`); wonum + fev/2026 → total 0 (filtro de data aplicado); `wonums=" , "` →
`required`. [[estado-do-projeto]].

## [2026-10-29] code | Allowlist com descrições próprias e filtro de argumentos
`allowlist.py`: `ToolSpec` com descrição rica (inglês) da ferramenta e dos 14
parâmetros; `AGENT_TOOLS` só com `script_queryworkorders` (`apischema` fica só no
Claude Code); `input_schema` fechado; `clean_arguments` recusa parâmetro fora do
schema, tipo inválido e texto longo. Testes amarram parâmetros/campos ao script.
59 testes. Gateway de LLM: usuário ainda decidindo. [[allowlist-somente-leitura]],
[[estado-do-projeto]].
