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

## [2026-10-29] session | Fim de sessão: merge na main
Branch `chore/esqueleto-inicial` integrada na `main` por fast-forward, push da
`main` e branch apagada (local e remoto). [[estado-do-projeto]] reescrito: histórico
do dia condensado em "Feito", seção Git atualizada, "Falta" reordenada (gateway
aguardando decisão do usuário).

## [2026-10-29] analysis | Plano de ferramentas por automation script
Tabela "Fase 2" (18 ferramentas) separada em dados (script), cálculo (`analysis/`) e
texto (LLM). Usuário: focar nos scripts; ordem QUERYASSETS → QUERYFAILUREREPORTS →
`text` no QUERYWORKORDERS; bloco comum copiado; "histórico" coberto combinando OS e
ativos. `apischema` MXAPIASSET mostrou matriz de criticidade própria da Itambé
(`cci_*`). [[ferramentas-maximo]].

## [2026-10-29] code | QUERYASSETS escrito (não instalado)
`maximo_scripts/queryassets/`: script com bloco comum, response schema, README,
INSTALACAO. 13 parâmetros (filtros de lista, `ancestor` via ASSETANCESTOR, `text` por
palavras), permissão ASSET/READ no código, sem data obrigatória (pendente confirmação).
Allowlist com `script_queryassets`. `test_script_common.py` aplica a todos os scripts
as regras de ASCII, imports, `globals()` e escrita. 92 testes. Branch
`feat/queryassets`, sem commit. [[ferramentas-maximo]], [[estado-do-projeto]].

## [2026-10-29] decision | Cadastro sem intervalo de datas
Usuário confirmou: `QUERYASSETS` sem data obrigatória; datas obrigatórias só em
consultas de movimento. `CLAUDE.md`, `maximo_scripts/README.md`,
[[automation-scripts-como-ferramentas]] e [[ferramentas-maximo]] atualizados. Commit
na `feat/queryassets` autorizado; usuário vai instalar em homologação.

## [2026-10-29] test | QUERYASSETS validado em homologação
Usuário instalou. 1ª chamada: BMXAA10147E nas duas ferramentas (usuário da chave em
PT de novo); usuário trocou para EN e passou. Checklist do README conferido via
cliente avulso (Claude Code não via a ferramenta nova sem reiniciar): total 14709,
`assetnums`, `text` (acento precisa bater), hierarquia em vários níveis, campos
bool/data/número, página 2, erros. Achado: `ancestor` incluía o próprio ativo;
SQL corrigido (`aa.assetnum <> aa.ancestor`), falta reinstalar. [[mas-mcp-server]],
[[estado-do-projeto]], [[ferramentas-maximo]].

## [2026-10-29] test | QUERYASSETS reinstalado com correção do ancestor
`ancestor` conferido: CCM2.1 → 21, ACI0008 → 2, os dois → 23, ativo sem filhos → 0.
`QUERYASSETS` funcionando via MCP. [[ferramentas-maximo]], [[estado-do-projeto]].

## [2026-10-29] git | feat/queryassets integrada na main
Fast-forward da `main` até `feat/queryassets` (5 commits) e commit do estado no
`CLAUDE.md`. Push feito pelo usuário; branch ainda existe localmente.
[[estado-do-projeto]].

## [2026-10-29] git | Push e fim de sessão
Push da `main`; `feat/queryassets` apagada. Próxima sessão: `QUERYFAILUREREPORTS`.
[[estado-do-projeto]].

## [2026-10-30] chore | virtualenv atualizado
`uv lock --upgrade-package virtualenv`: 21.14.12 → 21.15.1 (alerta do Dependabot).
92 testes e pre-commit ok. Commit na `main`. [[estado-do-projeto]].

## [2026-10-30] decision | QUERYFAILUREREPORTS cancelado
Consultor funcional: Itambé não usa classe de falha. Ferramenta não será feita;
próximo passo vira `text` no `QUERYWORKORDERS`. Colunas da FAILUREREPORT
registradas para uso futuro. [[ferramentas-maximo]], [[estado-do-projeto]].

## [2026-10-30] code | text no QUERYWORKORDERS e bloco comum
`QUERYWORKORDERS` reescrito sobre o bloco comum; `parse_text` e `add_text_filter`
movidos para o bloco (`QUERYASSETS` sem mudança de comportamento). Allowlist com
`text`. Versão antiga e nova comparadas com as mesmas entradas: mesmo SQL, binds,
erros e resposta. 101 testes. [[ferramentas-maximo]].

## [2026-10-30] test | text validado em homologação
Usuário adicionou a variável e colou os dois scripts. MCP Server levou ~4 min para
ver o parâmetro. `text` publicado sem `u200b`, 15 parâmetros. "vazamento" → 92,
"vazamento oleo" → 3, `a`/`100%` → `invalid_text`, sem datas → `required`, sem
`text` → 18337 (igual). `QUERYASSETS`: 14709, CCM2.1 → 21. Achados: corretiva `CO`,
OS sem tipo, OS de checklist. [[itambe-cimentos]], [[estado-do-projeto]].

## [2026-10-30] git | feat/queryworkorders-text integrada na main
Commit e fast-forward na `main`; push pendente. [[estado-do-projeto]].

## [2026-10-30] synthesis | Prompts de teste de OS e ativos
32 prompts (OS, ativos, combinados, limites e segurança) para o usuário testar no
Claude Code; nova página [[prompts-de-teste]]. `.mcp.json` não conectou (Claude Code
aberto sem as variáveis; usar `scripts/claude-maximo.ps1`); conector do claude.ai
ativo. Push da `main` confirmado. [[estado-do-projeto]].

## [2026-11-03] code | QUERYJOBPLANS escrito
Decisões do usuário: `include_tasks`, filtros `assetnum`/`location` (JPASSETSPLINK),
`description_longdescription`, status padrão ACTIVE. Colunas conferidas no `apischema`
MXAPIJOBPLAN. Script com bloco comum, schema, README, `INSTALACAO.md`, allowlist e
testes (133). Branch `feat/queryjobplans`, sem commit. Falta instalar.
[[ferramentas-maximo]], [[estado-do-projeto]].

## [2026-11-03] test | QUERYJOBPLANS validado em homologação
Usuário instalou. Cliente avulso: 12 parâmetros; 2025 ACTIVE (sinônimo ATIVO), 2102
com ALL, 203 planos sem site; texto longo, filtros e erros ok. `include_tasks` deu
NullPointerException (JOBTASK sem JOBPLAN dono); corrigido com relação temporária
`$QJPTASKS`, reinstalado e ok. `assetnum` não conclusivo. Title das MCP Tools com
`u200b`. [[automation-scripts-como-ferramentas]], [[itambe-cimentos]],
[[estado-do-projeto]].

## [2026-11-03] git | feat/queryjobplans integrada na main
Dois commits (script + docs) e fast-forward na `main`; push pendente.
[[estado-do-projeto]].

## [2026-11-03] git | Push e limpeza de branches
Push da `main`; `feat/queryjobplans` e `feat/queryworkorders-text` apagadas (locais).
Só a `main`, sincronizada. [[estado-do-projeto]].

## [2026-11-03] synthesis | Fim de sessão
Estado com próximo passo (decisão do usuário: CLI `call_tool`, histórico de status,
`QUERYWOMATERIALS` ou gateway), perguntas ao consultor (códigos `PS1486`, ligação
plano–ativo) e aviso de que o cliente avulso de teste ficou só no scratchpad.
[[estado-do-projeto]].

## [2026-11-04] test | QUERYJOBPLANS: plano ligado à location
Usuário: Itambé liga plano à location. `location=L3T05M1` → 8 planos; `assetnum` dos
3 ativos dela (ACI0343, MCA5853, PEL0151) → 0. Descrição do `assetnum` na allowlist
manda buscar a location do ativo quando vier vazio. README do script, [[ferramentas-maximo]],
[[itambe-cimentos]], [[estado-do-projeto]] e CLAUDE.md atualizados.

## [2026-11-04] code | QUERYWOSTATUS escrito, instalado e validado
Decisão do usuário: histórico de status em 2 scripts (WOSTATUS agora, ASSETSTATUS
depois). Colunas: ASSETSTATUS no `apischema`; WOSTATUS sem estrutura de objeto.
Instalação: `chengeby` digitado errado (recriado), `u200b` na Description. Filtros e
erros ok. Mês levava 196 s: índice `SITEID, CHANGEDATE, WONUM` sem site na consulta;
site explícito → 4 s (366 dias, 50204 mudanças, 4 s). 163 testes. Branch
`feat/querywostatus`. [[ferramentas-maximo]], [[automation-scripts-como-ferramentas]],
[[estado-do-projeto]].

## [2026-11-04] test | Descrição da MCP Tool vem da Description do script
`u200b` da Description do `QUERYWOSTATUS` sumiu após redigitar e esperar o polling.
Texto redigitado ficou com erros ("statushistor:", sem espaços; cosmético, corrigir
no Maximo). `feat/querywostatus` integrada na `main` (fast-forward), branch apagada,
push pendente. [[automation-scripts-como-ferramentas]], [[estado-do-projeto]].

## [2026-11-04] code | QUERYASSETDOWNTIME escrito, instalado e validado
ASSETSTATUS (colunas do `apischema` `MXAPIASSETSTATUS`, sem esperar índices). 12
parâmetros, `event=down|up`, `assetnums`/`wonums` sem datas, site explícito, READ em
ASSET. Validado via MCP: filtros, paginação, erros, ~2 s em 366 dias. Regra do
`downtime` no retorno confirmada; `downtime` nem sempre bate com as datas; pares
repetidos; pouquíssimos dados na homologação. Description com `YYYY-NN-DD`
(corrigir). 194 testes. Commit `34fe200` na `main`. [[ferramentas-maximo]],
[[itambe-cimentos]], [[estado-do-projeto]].

## [2026-11-04] code | QUERYWOMATERIALS e QUERYMATUSAGE escritos e instalados
Decisão do usuário: material em 2 scripts (planejado + saldo; consumo real), datas
pela OS no planejado. Ligação com OS-topo por `wogroup`. `QUERYMATUSAGE` validado via
MCP: 5241 transações em 366 dias (0,4 s), filtros, campos, erros. Achado: `linecost`
com sinal oposto ao de `quantity` (docs e allowlist corrigidos). `QUERYWOMATERIALS`:
erros ok, WPMATERIAL vazio em homologação (sem OS com material planejado), dados não
validados. 255 testes. Branch `feat/querywomaterials`. [[ferramentas-maximo]],
[[itambe-cimentos]], [[estado-do-projeto]].

## [2026-11-04] decision | Itambé não planeja material no Maximo
Usuário: a Itambé não aponta material planejado no Maximo (WPMATERIAL vazio também em
produção). `QUERYWOMATERIALS` sem uso na Itambé; consumo via `QUERYMATUSAGE`.
[[itambe-cimentos]], [[estado-do-projeto]].

## [2026-11-04] code | QUERYWOMATERIALS fora dos agentes
Decisão do usuário: tirar dos agentes, manter no repo. Allowlist ganha `DORMANT_TOOLS`
(leitura liberada no Claude Code, `clean_arguments` recusa). 256 testes.
[[allowlist-somente-leitura]], [[ferramentas-maximo]], [[estado-do-projeto]].

## [2026-11-04] git | feat/querywomaterials integrada na main
Usuário desativou a MCP Tool do `QUERYWOMATERIALS` no Maximo da Itambé. Commit e
fast-forward da `main`; push pendente. [[estado-do-projeto]].

## [2026-11-04] decision | Gateway de LLM = LangChain; gateway escrito
Usuário decidiu: interface de modelos do LangChain como gateway. Chave do Claude a
confirmar. `llm/gateway.py` com `anthropic` e `ollama`, configuração `LLM_*`, testes
sem chave (268). Branch `feat/llm-gateway`. Próximo: 1º agente com LangGraph.
[[estado-do-projeto]].

## [2026-11-04] decision | Análises antes dos agentes; backlog primeiro
Usuário: fazer `analysis/` antes do agente; 1ª análise = backlog de OS. Sondagem de
18152 OS (1 ano): status próprios da Itambé (CONCL, APROG, POSEXEC, EMAND...),
worktype `MS` dominante, 4598 sem tipo. Ler 1 ano pelo MCP: 202 s (37 páginas).
Pendente: classificação dos status (aberta/fechada/cancelada) e significado de `MS`;
investigar índice/site explícito no `QUERYWORKORDERS`. Push da `main` pendente (2
commits). [[estado-do-projeto]], [[itambe-cimentos]].

## [2026-11-04] git | Push da main
Push de `4bc978a`, `0cc4b0f` e `936399c` (`a5ca255..936399c`); `main` sincronizada.
[[estado-do-projeto]].

## [2026-11-06] update | Pendências resolvidas pelo usuário
Lentidão do `QUERYWORKORDERS` resolvida; `QUERYMATUSAGE.py` e schema recolados;
Description do `QUERYASSETDOWNTIME` corrigida. Forma da correção da lentidão a
registrar (repo sem `siteid` explícito). [[estado-do-projeto]].

## [2026-11-06] update | Lentidão do QUERYWORKORDERS: passar siteid
Usuário: sem índice novo; passar `siteid` na chamada deixa a consulta rápida. Script
igual ao repo (subconsulta de `siteauth`). Conferido via MCP: 1 ano por `reportdate`,
18152 OS, 37 páginas, sem erro. Proposta: sites explícitos no script, como no
`QUERYWOSTATUS`. [[estado-do-projeto]].

## [2026-11-06] code | QUERYWORKORDERS com sites explícitos
Branch `perf/queryworkorders-explicit-sites`: sem `siteid`, o script lê os sites
autorizados (SITE) e põe `siteid in (...)`; sem site autorizado, `not_authorized`.
Mesmo código do `QUERYWOSTATUS`. 272 testes. Falta recolar no Maximo e medir.
[[estado-do-projeto]], [[automation-scripts-como-ferramentas]].

## [2026-11-06] update | Lentidão do QUERYWORKORDERS encerrada; site MINERACAO
Script com sites explícitos recolado pelo usuário; total 18152 sem `siteid`.
Medição (pág. 1 de 500): sem `siteid` (MAXADMIN, todos os sites) ~4 s; 2 sites
~1,5 s; 2 + 18 sites falsos ~4 s (lista longa larga o índice). Usuário: não é
problema, alguns segundos não afetam o funcionamento. Achado: 2º site `MINERACAO`
(734 OS no ano); só `FABRICA` perde 4%. [[estado-do-projeto]], [[itambe-cimentos]].

## [2026-11-06] decision | Classificação de status da OS (Itambé)
Domínio SYNONYM (21 valores, tela do usuário). Classe pelo valor interno, exceções
por cliente: POSEXEC = "executada" (separada do backlog, usuário), PREVCAN =
cancelada. APROG sem valor interno visto (aberta). Worktypes: hipóteses pelas
descrições (`MS` rotina preventiva que parece ter virado `MPV`). Usuário da chave
voltou a PT (BMXAA10147E, 3ª vez) e foi reposto em EN. [[itambe-cimentos]],
[[estado-do-projeto]].

## [2026-11-06] code | Backlog de OS em analysis/
Branch `feat/analysis-backlog`: configuração por cliente (TOML), busca pelo MCP com
allowlist, pandas, CLI. Idade pelo `reportdate` (usuário). Homologação: 6989 abertas
(5610 com 181-365 dias, MS 5799), `persongroup` sempre vazio; POSEXEC 109420 desde
2007, só contadas. Dados desde 2006. Pandas 3.1.1 adicionado. 307 testes.
[[estado-do-projeto]], [[itambe-cimentos]].

## [2026-11-06] decision | Homologação é base de teste; sem data de corte
Usuário: POSEXEC não é fim de processo; o backlog da homologação é lixo do processo
antigo (OS não fechadas). Homologação só para testes e desenvolvimento: números do
backlog validam o código, não o negócio. Não definir data de início do processo novo.
[[estado-do-projeto]], [[itambe-cimentos]].

## [2026-11-06] code | Reincidência de corretivas em analysis/
Branch `feat/analysis-recurrence`: por ativo e location (site + código), canceladas
fora, reincidência em até 30 dias, intervalo mediano. Tipos corretivos por cliente
(Itambé CO, EM). Homologação: 964 corretivas, 144 ativos com 2+, MOI0001 22 falhas;
muitas CO são inspeção/checklist/teste. 313 testes. [[estado-do-projeto]].

## [2026-11-06] code | Tempo em status em analysis/
Branch `feat/analysis-status-time`: OS com 1ª conclusão no período, histórico
completo por `wonums` (QUERYWOSTATUS, lotes de 50 por site), vida até a 1ª conclusão;
lead time, dias por status e classe, transições, OS mais demoradas. Paginação comum
`fetch_all_pages`. Homologação: 90 dias 230 OS em 4 s; 365 dias 13608 OS, 41078
mudanças em 155 s, EMAND 47% do tempo. Status `AMATER` fora do domínio: usuário
confirmou aguardando material antigo, entrou no `itambe.toml` como aberto. 318 testes.
[[estado-do-projeto]], [[itambe-cimentos]].

## [2026-11-06] code | Consumo de material em analysis/
Branch `feat/analysis-material`: transações do QUERYMATUSAGE no período + OS delas
por `wonums` (tipo, ativo, location). Custo líquido, devolução pelo sinal, Pareto,
por tipo da OS, item, ativo, location, OS, almoxarifado e mês. Homologação (1 ano):
9,84 mi líquidos, 5127 transações, 18 s; MP 47%, sem tipo 34%, CO 4%; MOI0012 36,5%;
144 itens = 80% do custo. As 4 análises planejadas feitas. 324 testes.
[[estado-do-projeto]], [[itambe-cimentos]].

## [2026-11-06] code | 1º agente (Análise de OS) sem chave de API
Pergunta do usuário: desenvolver sem LLM por API, testando no Claude Code. Feito em
3 camadas: `agents/tools.py` (análises como ferramentas, `Toolbox` com erros
seguros), `agents/graph.py` (LangGraph, 5 rodadas, testes com modelo falso),
servidor MCP local `analises` + subagente `.claude/agents/analise-os.md` gerado da
receita. Dependência `langgraph` 1.2. Servidor testado na homologação. 350 testes.
[[agente-sem-chave-de-api]], [[estado-do-projeto]].

## [2026-11-06] test | Agente analise-os com perguntas de gerente
6 perguntas no subagente (backlog, reincidência, material, pedido de escrita, MTBF,
prompt injection). Números conferidos contra a CLI: todos batem. Recusas corretas.
Ajustes pendentes: escala de prioridade e EMAND no contexto do cliente, status ×
idade no backlog, sem detalhe interno na recusa, tratar por "você". Perguntas 33-38
em [[prompts-de-teste]]. [[agente-sem-chave-de-api]], [[estado-do-projeto]].

## [2026-11-06] code | Receita analise-os: regras 9 e tratamento
Regra 9 (não falar de implementação interna) e tratar o gerente por "você".
Subagente gerado de novo, 350 testes. Reteste: "você" ok; injection ainda cita
arquivos porque o subagente do Claude Code herda `CLAUDE.md` e git status.
[[agente-sem-chave-de-api]].

## [2026-11-06] code | Backlog: status × idade
Cada status do backlog ganhou `by_age_days` (mesmas faixas da idade); tabela "Status x
idade" na CLI; descrição da ferramenta `analyze_work_order_backlog` atualizada.
Homologação: AAPROV > 365 d = 37; colunas fecham com os totais (>365 = 720).
Servidor `analises` só carrega o código novo após reiniciar o Claude Code.
[[agente-sem-chave-de-api]], [[estado-do-projeto]].

## [2026-11-06] test | Reteste do agente analise-os
Após reiniciar o Claude Code (servidor `analises` com status × idade): perguntas 33,
39 (nova, status × idade) e 38. Números iguais à CLI; 27 corretivas abertas em 12
meses conferidas no Maximo. Injection recusou sem detalhe interno. Pendentes na
receita: "em média (mediana)" e máximo de dias no status atribuído a uma OS.
[[agente-sem-chave-de-api]], [[prompts-de-teste]], [[estado-do-projeto]].

## [2026-11-06] code | Receita analise-os: regra 10
Medida pelo nome da ferramenta ("mediana", nunca "média") e mediana/máximo/total de
grupo não atribuídos a uma OS, ativo ou item. Subagente gerado de novo, 350 testes.
Reteste só após reiniciar o Claude Code. [[agente-sem-chave-de-api]].

## [2026-11-06] test | Reteste da regra 10 e regra 11
Perguntas 33, 39 e 40 (nova: lead time em 90 dias) no subagente. Números iguais à
CLI; regra 10 ok (mediana pelo nome, valores de grupo não atribuídos a OS). Desvio
novo: tipo `MP` chamado de "melhoria" → regra 11 na receita (não deduzir significado
de código que o contexto do cliente não explica). Subagente gerado de novo, 350
testes. Reteste só após reiniciar o Claude Code. [[agente-sem-chave-de-api]],
[[prompts-de-teste]], [[estado-do-projeto]].

## [2026-11-06] test | Reteste da regra 11 e moeda no contexto
Perguntas 40 e 35 no subagente. Números iguais à CLI. Regra 11 ok: `MP` só citado
como código, status sem significado inventado. Desvios: "R$" sem moeda no contexto
e "troca planejada" (insinua `MP` = preventiva). Moeda: `currency` opcional (ISO 4217)
no config do cliente (Itambé BRL); contexto diz a moeda ou manda dar valores sem
símbolo. Significado dos tipos de trabalho (`MP`, `MS`, `MPR`, `FAB`) a pedir ao
consultor. 355 testes. Reteste só após reiniciar o Claude Code.
[[agente-sem-chave-de-api]], [[prompts-de-teste]], [[estado-do-projeto]].
