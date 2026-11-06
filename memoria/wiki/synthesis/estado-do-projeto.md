---
title: Estado do projeto
type: synthesis
sources: []
related: [[mas-mcp-server]], [[allowlist-somente-leitura]], [[automation-scripts-como-ferramentas]], [[chave-api-por-usuario]], [[doc-mcp-server]], [[guia-automation-scripts]]
created: 2026-10-21
updated: 2026-11-06
---

# Estado do projeto

Ler no início de cada sessão. Atualizar no fim.

## Onde paramos (2026-11-06, agente)

- **1º agente (Análise de OS) começado sem chave de API** (pergunta do usuário):
  ver [[agente-sem-chave-de-api]]. `agents/tools.py` (4 análises como ferramentas
  `analyze_*` + `script_*` com `clean_arguments`), `agents/recipes.py` (receita
  `analise-os`, contexto do cliente do TOML), `agents/graph.py` (LangGraph 1.2,
  5 rodadas), `agents/mcp_server.py` (servidor local `analises` em `.mcp.json`),
  `agents/claude_agent.py` (gera `.claude/agents/analise-os.md`). 350 testes.
  Teste real do servidor por stdio OK (0,6 s).
- **Teste com perguntas de gerente feito (2026-11-06):** 6 perguntas no subagente
  `analise-os` (backlog, reincidência, material, pedido de escrita, MTBF, prompt
  injection). Números conferidos contra a CLI: todos batem; recusas certas. Ver
  [[agente-sem-chave-de-api]] e perguntas 33-38 em [[prompts-de-teste]].
- **Próximo:** ajustes do teste: escala de prioridade e significado de EMAND no
  contexto do cliente (confirmar com o consultor). Status × idade no backlog
  feito (`by_status[status].by_age_days`; AAPROV > 365 d = 37). Regras na receita (não falar de implementação interna; tratar por
  "você") feitas; a de implementação interna só valida no grafo (o subagente herda
  `CLAUDE.md`). Chave do Claude ainda a confirmar (agente real no grafo, evals).

## Antes: análises (2026-11-04 a 2026-11-06)

- **Decisão do usuário: antes dos agentes, scripts de análise (`analysis/`).** Primeira
  análise escolhida: **backlog de OS** (abertas por idade, status, tipo, prioridade,
  equipe, ativo/location). Outras opções oferecidas e não escolhidas ainda: tempo em
  status, reincidência de corretivas, consumo/custo de material.
- **Arquitetura proposta para `analysis/`** (sem objeção do usuário): dados pelo MCP
  com as ferramentas atuais (todas as páginas, com limite), contas em pandas
  (funções puras, testadas com dados sintéticos), CLI
  `uv run python -m maximo_agents.analysis ...` para o usuário conferir números contra
  o Maximo; depois o agente chama as mesmas funções. Nada escrito ainda.
- **Sondagem (18152 OS, `reportdate` 2025-11-05 a 2026-11-04):** status próprios da
  Itambé (ver [[itambe-cimentos]]). Script devolve o valor externo, então
  "aberta/fechada/cancelada" vira **configuração por cliente** no repo.
  **Classificação decidida (2026-11-06):** pelo valor interno do domínio SYNONYM
  (padrão do Maximo) com exceções por cliente; Itambé: POSEXEC como classe própria
  "executada" (fora do backlog aberto), PREVCAN como cancelada. Tabela em
  [[itambe-cimentos]]. Falta só o valor interno do APROG (aberta de qualquer jeito).
  Worktypes com hipóteses pelas descrições (`MS` parece ter virado `MPV`); confirmar
  com o consultor.
- **Backlog de OS feito (2026-11-06)**, branch `feat/analysis-backlog`, 307 testes:
  `analysis/config.py` + `clients/itambe.toml` (status → classe pelo valor interno,
  sites, `history_start` 2006-01-01), `analysis/fetch.py` (janelas de 366 dias, todas
  as páginas, limite 50 mil, só ferramentas da allowlist), `analysis/backlog.py`
  (pandas: idade pelo `reportdate`, decisão do usuário; dias no status pelo
  `statusdate`; por status, tipo, prioridade, equipe, site, location; 10 mais antigas),
  `mcp/session.py` (sessão MCP reutilizável), CLI `uv run python -m
  maximo_agents.analysis backlog [--as-of] [--since] [--json]`. 27 s na homologação.
- **Números da homologação (2026-11-06):** **6989 abertas** (mediana 232 dias):
  0-30 d 328, 31-90 d 264, 91-180 d 67, **181-365 d 5610**, >365 d 720. APROG 4271,
  EMAND 2282, AAPROV 239. Tipo **MS 5799** (lote de preventivas de rotina geradas
  ~mar/2026 e não executadas?), sem tipo 384, MPV 318. **`persongroup` vazio em
  todas** (Itambé não usa equipe na OS). Prioridade vazia 2730. FABRICA 6867,
  MINERACAO 122. Mais antigas: testes de interface de 2009 em AAPROV.
- **POSEXEC = acúmulo histórico:** **109420 OS** desde 2007, 4 a 8 mil por ano
  (~22% das OS); 106894 com mais de 1 ano. Executadas só **contadas** por faixa de
  idade (total do script), sem baixar as OS.
- **Usuário (2026-11-06):** POSEXEC **não** é fim de processo; as OS do backlog da
  homologação são lixo do processo antigo da Itambé, que não fechava as OS.
  **Homologação é ambiente só de testes e desenvolvimento:** os números servem para
  validar o código, não descrevem o backlog real (só em produção). **Sem data de
  corte** do processo novo (usuário não sabe e não precisa definir).
- **Reincidência de corretivas feita (2026-11-06)**, branch
  `feat/analysis-recurrence`, 313 testes: `analysis/recurrence.py` (canceladas fora;
  por ativo e por location, chave site + código; falhas, reincidências em até 30
  dias, intervalo mediano, última OS; por tipo, status e mês), `corrective_worktypes`
  no TOML (Itambé: CO, EM), `fetch_corrective_work_orders`, CLI `uv run python -m
  maximo_agents.analysis recurrence [--days 365] [--repeat-days 30] [--top 20]`. 2 s.
- **Homologação (2025-11-07 a 2026-11-06):** 964 corretivas (CO 931, EM 33); 165 sem
  ativo, 1 sem location; buraco abr-jun/2026. 358 ativos com corretiva, 144 com 2+,
  355 reincidências. Top: MOI0001 22 (mediana 5,2 d), BMB0126 18, CTS0032 16,
  FOR0001 16. Achado: muitas CO são "INSPEÇÃO ." e itens de checklist ("HÁ
  VAZAMENTO...? = SIM", "NÃO CONFORME:") ou testes ("TESTE EM"); várias OS no mesmo
  instante (mediana 0 d). Em produção, conferir se CO = falha real.
- **Tempo em status feito (2026-11-06)**, branch `feat/analysis-status-time`, 318
  testes: `analysis/status_time.py`. Coorte = OS cuja **1ª conclusão** (status da
  classe closed) caiu no período; histórico **completo** de cada uma por `wonums`
  (lotes de 50 por site, sem censura de início). Vida da OS = 1ª mudança registrada
  até a 1ª conclusão (fechar depois de concluir não conta). Relatório: lead time
  (mediana, p90, média), dias por classe e por status (% do tempo total, mediana,
  p90, máx), transições, OS mais demoradas com o caminho, quem concluiu, por mês.
  `fetch_completed_histories` + `fetch_all_pages` (paginação comum). CLI `uv run
  python -m maximo_agents.analysis status-time [--days 90] [--worktype CO,EM]
  [--top 20]`.
- **Homologação:** 90 dias → 230 OS, 873 mudanças, 4 s (fechamento em massa
  MAXADMIN em 09/10, ciclos de horas: dado de teste). 365 dias → 13608 OS, 41078
  mudanças, **155 s**; lead time mediana 35,9 d, p90 280 d; EMAND 47% do tempo, APROG
  32%, POSEXEC 12%. Status `AMATER` (fora do domínio atual) = aguardando material
  antigo, confirmado pelo usuário; configurado como aberto (ver [[itambe-cimentos]]).
  Perto do limite de 50 mil registros com 1 ano; períodos maiores pedem
  `--max-records`.
- **Consumo de material feito (2026-11-06)**, branch `feat/analysis-material`, 324
  testes: `analysis/material.py`. Transações do `QUERYMATUSAGE` no período
  (`actualdate`, sites do cliente, com ou sem OS) + OS delas pelo `QUERYWORKORDERS`
  por `wonums` (tipo, ativo, location, descrição; lotes de 50 por site,
  `wonum_batches` comum). Custo líquido = soma(`linecost`), devolução pelo sinal da
  quantidade (não pelo rótulo do `issuetype`, que é PT). Ativo/location da transação
  ou, se vazio, da OS. Relatório: totais, por tipo da OS (`(sem OS)`, `(OS não
  encontrada)` = tarefa), almoxarifado, mês, Pareto 80%, itens, ativos, locations
  (com item de maior custo) e OS. CLI `uv run python -m maximo_agents.analysis
  material [--days 365] [--top 20]`. **18 s** em 1 ano. Números em [[itambe-cimentos]].
- **As 4 análises planejadas estão feitas.** Próximo: primeiro agente.
- **Lentidão do `QUERYWORKORDERS`: encerrada, não é problema** (usuário, 2026-11-06):
  são alguns segundos por página e não afetam o funcionamento. Histórico: 1 ano pelo
  MCP levou 202 s (37 páginas de 500, ~5,5 s cada). Script passou a pôr os sites
  autorizados explícitos (`siteid in (...)`, como no `QUERYWOSTATUS`), recolado no
  Maximo. Medição 2026-11-06 (pág. 1 de 500): sem `siteid` (MAXADMIN, todos os
  sites) ~4 s; `FABRICA,MINERACAO` ~1,5 s; os mesmos 2 + 18 sites falsos ~4 s. Lista
  longa faz o banco largar o índice; gerente com 1 a 3 sites deve ficar perto de 1,5 s
  (medir quando houver chave de gerente). Sem índice novo no banco.
- **Itambé tem 2 sites com OS:** `FABRICA` (17418 OS no ano) e **`MINERACAO`** (734).
  `siteid=FABRICA` sozinho perde 4% das OS: em `analysis/`, não passar só FABRICA.
  Backlog segue buscando só status abertos, por janelas de 366 dias.
- Sondas no scratchpad (`call_tool.py`, `probe_status.py`) somem com a sessão; reforça
  o CLI `call_tool` no repo.

### Antes, no mesmo dia: gateway de LLM

- **Gateway de LLM decidido e feito** (usuário: LangChain como gateway). Commit
  `0cc4b0f` na `main`: `llm/gateway.py` (`create_chat_model`, provedores
  `anthropic`/`ollama` por `LLM_PROVIDER`/`LLM_MODEL`, erro sem segredo), campos `llm_*`
  no `Settings`, `.env.example`. Dependências `langchain-core`, `langchain-anthropic`,
  `langchain-ollama`. 268 testes.
- **Chave do Claude:** usuário vai confirmar. Máquina de dev sem Ollama e sem GPU
  (Ollama em CPU só para montar código, não para avaliar qualidade).
- Agente (LangGraph, cliente MCP + allowlist, 5 voltas, testes com
  `GenericFakeChatModel`) fica **depois** das análises (decisão do usuário).

### Antes, no mesmo dia: material

- **Material em 2 scripts** (commit `4bc978a` na `main`):
  - `QUERYMATUSAGE` (MATUSETRANS) **funcionando via MCP**: 5241 transações em 366
    dias, 0,4 s; `issuetype`, `wonums` (ligação por `wogroup`), `worktype`, todos os
    campos e erros conferidos. Achado: `linecost` tem sinal oposto ao de `quantity`
    (allowlist, README, schema e comentário corrigidos; **usuário recolar script e
    schema** para ficarem iguais ao repo, sem urgência).
  - `QUERYWOMATERIALS` (WPMATERIAL + saldo INVBALANCES) instalado; erros/limites ok,
    mas **WPMATERIAL vazio em homologação**: dados, `taskid`, saldo e campos não
    validados. Validar quando houver material planejado (produção ou OS de teste).
    Description corrigida pelo usuário (tinha "materails").
  - 255 testes. Cliente de teste avulso refeito no scratchpad (`call_tool.py`).
- **Itambé não planeja material no Maximo** (usuário): `QUERYWOMATERIALS` fora dos
  agentes (`DORMANT_TOOLS`; decisão do usuário), fica no repo para outros clientes.
  MCP Tool desativada no Maximo da Itambé pelo usuário. 256 testes.

### Antes, no mesmo dia: QUERYASSETDOWNTIME

- **`QUERYASSETDOWNTIME` funcionando via MCP** (commit `34fe200` na `main`, push
  pendente). ASSETSTATUS: uma linha por queda/retorno do ativo; datas em
  `changedate` (máx 366 dias) ou `assetnums`/`wonums`; `event=down|up` (SQL fixo);
  READ em ASSET; site explícito. 194 testes. Colunas do `apischema`
  (`MXAPIASSETSTATUS`). Regra confirmada: queda `isrunning` falso e `downtime` 0;
  retorno `isrunning` verdadeiro com as horas. Cerca de 2 s em 366 dias.
- **Dados de parada na Itambé (homologação):** quase nada (~120 linhas; 4 em 2025,
  0 em 2026). `downtime` gravado nem sempre bate com as datas (MCC2213: 2h56 → 2.0);
  pares repetidos (ACI1020, 5 iguais); linha de cadastro sem queda. Deduplicar no
  `analysis/`. **Perguntar ao consultor** se registram paradas em produção antes de
  prometer MTTR/disponibilidade.
- **Pendente do usuário no Maximo:** Description do `QUERYASSETDOWNTIME` com
  `YYYY-NN-DD` (corrigir para `YYYY-MM-DD`); Log Level ERROR nos scripts.
- **Próximo passo:** usuário decide. Opções: `QUERYWOMATERIALS`, CLI `call_tool` no
  repo, primeiras análises em `analysis/` (tempo em status, horas paradas), gateway
  de LLM (aguarda decisão).

### Antes, no mesmo dia: QUERYWOSTATUS

- **`QUERYWOSTATUS` funcionando via MCP** (`feat/querywostatus` integrada na `main`
  por fast-forward, branch apagada; push feito, `2a9dd24`). Decisão do usuário: histórico de status em 2 scripts novos
  (`QUERYWOSTATUS` agora, `QUERYASSETDOWNTIME` depois), não opção das atuais.
  Uma linha por mudança (WOSTATUS); datas em `changedate` (máx 366 dias) ou
  `wonums`; filtros da OS por subconsulta. 163 testes. Detalhes em
  `maximo_scripts/querywostatus/README.md`.
- **Lição de desempenho:** índice por data da WOSTATUS é `SITEID, CHANGEDATE,
  WONUM`; sem site na consulta o banco varria a tabela (outubro: 196 s). Script
  agora lê os sites autorizados e põe `siteid in (...)` explícito: 4 s no mês, 4 s em
  366 dias (50204 mudanças). Conferir índices antes de cada script de movimento
  (ver [[automation-scripts-como-ferramentas]]).
- WOSTATUS não tem estrutura de objeto no `apischema` (HTTP 500 `mosInfo`); colunas
  confirmadas na 1ª chamada. ASSETSTATUS tem (MXAPIASSETSTATUS).
- Cliente de teste avulso refeito no scratchpad (`call_tool.py`); some com a sessão.
  Reforça o item "CLI `call_tool`" de "Falta".
- Achado: `QUERYWORKORDERS` dá 0 OS em 1 a 5/set/2026 (homologação); conferir se é
  buraco de dados.
- Description do `QUERYWOSTATUS` corrigida depois (MCP mostra o texto certo).

### Antes, no mesmo dia

- **Ligação plano–ativo respondida:** Itambé liga plano à **location**, não ao
  ativo (usuário). `QUERYJOBPLANS` com `location=L3T05M1` → 8 planos; `assetnum` dos
  3 ativos dela → 0. Filtro `location` validado; `assetnum` usa a mesma subconsulta
  (só muda a coluna), sem caso positivo na Itambé. Descrição do `assetnum` na
  allowlist ganhou dica: se vier vazio, buscar a location do ativo com
  `script_queryassets` e filtrar por location. 134 testes. Commit na `main`.
- **Pendente:** Title das MCP Tools `QUERYASSETS` e `QUERYJOBPLANS` com `u200b`
  (cosmético); Log Level do `QUERYJOBPLANS` e do `QUERYWORKORDERS` para ERROR.
- **Perguntar ao consultor:** códigos na descrição longa dos planos (ex.: `PS1486`).
- **Próximo passo:** usuário decide. Opções: CLI `call_tool` no repo; histórico de
  status (WOSTATUS/ASSETSTATUS); `QUERYWOMATERIALS`; gateway de LLM em espera.
- MCP do `.mcp.json` não conectou de novo (Claude Code aberto sem as variáveis);
  testes pelo conector `maximo` do claude.ai.

## Antes (2026-11-03)

- **`QUERYJOBPLANS` funcionando via MCP** em homologação (`feat/queryjobplans`
  integrada na `main`, com push; branch apagada). 2025 planos ACTIVE (Itambé
  grava o sinônimo ATIVO), 2102 com `status=ALL`, 203 sem site (nível sistema),
  tarefas, texto longo, filtros e erros ok. 1ª instalação: `include_tasks` dava
  NullPointerException (JOBTASK sem JOBPLAN dono); corrigido lendo as tarefas por
  relação temporária do plano. 134 testes. Detalhes em
  `maximo_scripts/queryjobplans/README.md` e [[ferramentas-maximo]].
- **Pendente:** ativo com plano ligado (JPASSETSPLINK) para validar `assetnum`, ou
  confirmar se a Itambé liga plano a ativo só pela PM; Title das MCP Tools
  `QUERYASSETS` e `QUERYJOBPLANS` com `u200b` (cosmético, redigitar); Log Level do
  `QUERYJOBPLANS` e do `QUERYWORKORDERS` de volta para ERROR.
- **Perguntar ao consultor:** o que são os códigos na descrição longa dos planos
  (ex.: `PS1486`; talvez procedimento de segurança) e se plano é ligado a ativo
  pela aba Job Plan do ativo ou só pela PM.
- Cliente avulso de teste ficou no scratchpad da sessão (`call_tool.py`: lista
  ferramentas, confere `u200b` e chama as da allowlist via `clean_arguments`);
  **some com a sessão**. Vale virar o CLI `call_tool` de "Falta" (item 4).
- **Próximo passo:** usuário decide ao retomar. Opções: CLI `call_tool` no repo;
  histórico de status (WOSTATUS/ASSETSTATUS); `QUERYWOMATERIALS` (ler filhos pelo
  dono, lição do JOBTASK); gateway de LLM segue em espera.

## Antes (2026-10-30)

- **Roteiro de testes:** 32 prompts de OS e ativos em [[prompts-de-teste]] para o
  usuário testar no Claude Code; semente de `tests/evals/`.
- **`.mcp.json` não conectou** nesta sessão (`'url' is not a valid URL`): Claude
  Code aberto sem `MAXIMO_MCP_URL`/`MAXIMO_API_KEY` no ambiente. Abrir por
  `scripts/claude-maximo.ps1`. Conector `maximo` do claude.ai seguiu ativo
  (`script_queryworkorders`, `script_queryassets`).
- Push da `main` feito (sincronizada com `origin/main`).
- `virtualenv` 21.15.1 no `uv.lock` (alerta do Dependabot); commit na `main`.
- **`QUERYFAILUREREPORTS` cancelado:** Itambé não usa classe de falha (consultor
  funcional). Ver [[ferramentas-maximo]].
- **`text` no `QUERYWORKORDERS` funcionando via MCP** (bloco comum, 15 parâmetros,
  sem `u200b`). "vazamento" → 92 OS em 12 meses; "vazamento oleo" → 3; erros ok;
  sem `text` igual a antes (18337). `QUERYASSETS` reinstalado com o bloco novo,
  mesmo resultado de 2026-10-29. Branch `feat/queryworkorders-text` integrada na
  `main` (sem push).
- **Achados nos dados (perguntar ao consultor):** tipo de trabalho corretivo é
  **CO** (não CM); 34 de 92 OS com "vazamento" **sem `worktype`**; muitas OS são
  itens de checklist ("NÃO CONFORME: HÁ VAZAMENTO NA TUBULAÇÃO?"). Contagem de
  falhas por palavra mistura inspeção com falha real. Ver [[itambe-cimentos]].
- **Pendente do usuário no Maximo:** Log Level do `QUERYWORKORDERS` de volta para
  ERROR; Description do script difere do `INSTALACAO.md` (antiga, sem "or wonums";
  não afeta o agente).
- **Próximo passo:** usuário decide ao retomar (gateway de LLM segue em espera;
  opções de script: histórico de status, `QUERYJOBPLANS`).

## Antes (2026-10-29, fim)

- **Novas ferramentas antes do gateway** (decisão do usuário): plano em
  [[ferramentas-maximo]]. `QUERYASSETS` na `main`, **instalado e
  validado via MCP** (14709 ativos, filtros, `text`, hierarquia, paginação, erros).
  Achado: `ancestor` trazia o próprio ativo (linha dele com ele mesmo em
  ASSETANCESTOR); corrigido no SQL, reinstalado e conferido (CCM2.1 → 21).
  **Próximo passo (sessão de 2026-10-30):** `QUERYFAILUREREPORTS` (FAILUREREPORT +
  WORKORDER, datas obrigatórias, WOTRACK/READ, bloco comum copiado), em branch nova;
  depois `text` no `QUERYWORKORDERS` (que então recebe o bloco comum).
- Teste sem reiniciar o Claude Code: cliente avulso no scratchpad chama ferramentas
  da allowlist (o Claude Code só vê ferramentas registradas antes do início da
  sessão). Item "CLI `call_tool`" de "Falta" ganha motivo.
- **`QUERYWORKORDERS` funcionando via MCP** em homologação (Claude Code → MCP Server
  → script): dados reais, paginação, filtros, validações e busca por `wonums` sem
  datas conferidos. Detalhes em [[automation-scripts-como-ferramentas]].
- **Allowlist pronta para o agente:** descrições próprias para o LLM,
  `input_schema` fechado e `clean_arguments` ([[allowlist-somente-leitura]]).
- 101 testes, Ruff e pre-commit ok.
- **Gateway de LLM em espera:** usuário ainda analisando a abordagem. Não começar
  sem decisão dele. Por isso o 1º agente também espera.

## Git

GitHub `Gustavo-FAC/maximo-ai-agents` (privado). 2026-11-04 (fim): `4bc978a`
(materiais), `0cc4b0f` (gateway) e `936399c` (wiki do fim do dia) na `main`, **com
push**; `main` sincronizada com `origin/main`. Branches `feat/querywomaterials` e
`feat/llm-gateway` apagadas. Só a `main`. 2026-11-03:
`feat/queryjobplans` integrada na `main` por fast-forward, com push. Branches locais
`feat/queryjobplans` e `feat/queryworkorders-text` apagadas. Só a `main`, sincronizada.
2026-10-30:
`feat/queryworkorders-text` integrada na `main` por fast-forward, com push
(`main` sincronizada). Branch ainda existe localmente. `chore/esqueleto-inicial` foi
integrada por fast-forward e apagada (local e remoto) em 2026-10-29.
`feat/queryassets` integrada na `main` por fast-forward em 2026-10-29, com push
(feito pelo usuário). Branch apagada. Só a `main`, sincronizada. Trabalho novo: branch nova a partir da `main`.

## Feito

- 2026-10-21: esqueleto do repo, `uv sync`, pre-commit (gitleaks + Ruff), testes.
- 2026-10-21: `check_connection` corrigido (SDK mcp 2.3, UTF-8) e rodado contra
  homologação Itambé: conexão OK, só `apischema`.
- 2026-10-21: memória do projeto em `memoria/` (este wiki).
- 2026-10-22: ingest de [[doc-mcp-server]] e [[guia-automation-scripts]].
- 2026-10-22: `maximo_scripts/queryworkorders/`: script Jython 2.7, response schema,
  README (especificação), `INSTALACAO.md` e testes da lógica pura.
  - Filtros só por bind; colunas de listas fixas; limites no script (366 dias,
    50 wonum, 20 por lista, 500 por página); `total` sempre devolvido.
  - Permissão WOTRACK/READ e sites autorizados checados no código.
- 2026-10-22: 1ª instalação → OAS revelou U+200B colado em nomes,
  `authapp`/`authsigoption` expostos como parâmetros, descrições cortadas em 100.
  Corrigido.
- Ruff: `maximo_scripts/**` ignora `UP`, `B904`, `S608` (Jython 2.7).
- 2026-10-29: Claude Code ligado ao MCP do Maximo: `.mcp.json` (URL e chave por
  variável de ambiente), `scripts/claude-maximo.ps1`, allowlist de nomes exatos e
  hook `claude_code_guard.py` (fail-closed); settings negam as 7 ferramentas padrão
  de escrita.
- 2026-10-29: `QUERYWORKORDERS` posto para rodar no Maximo. Sequência de erros e
  correções (detalhes em [[automation-scripts-como-ferramentas]]):
  1. BMXAA10147E com usuário da chave em PT → usuário em EN (observação em
     [[mas-mcp-server]], não pré-requisito).
  2. `No module named datetime` → classe `Day` própria (Jython sem biblioteca padrão).
  3. Resposta toda `null` → `OslcUtils.jsonToBytes` e variáveis implícitas lidas do
     escopo.
  4. HTTP 500 BMXAA1649E → `StackOverflowError` por `_scope = globals()` no topo;
     lógica movida para `_main`.
  5. `internal_error` → `ScriptService` sem `isLoggingEnabled`; removido.
- 2026-10-29: datas opcionais quando `wonums` vem preenchido (decisão do usuário),
  reinstalado e validado.
- 2026-10-29: allowlist com descrições próprias, `input_schema` e
  `clean_arguments`; `apischema` só no Claude Code, fora dos agentes.
- 2026-10-29: merge na `main`, push, branch antiga apagada.
- 2026-10-29: `QUERYASSETS` escrito, instalado, validado via MCP; `ancestor` sem o
  próprio ativo. `feat/queryassets` integrada na `main`, com push.
- 2026-10-30: `virtualenv` 21.14.12 → 21.15.1 (Dependabot, alta); 92 testes e
  pre-commit ok.
- 2026-10-30: `QUERYFAILUREREPORTS` cancelado (Itambé não usa classe de falha).
- 2026-10-30: `text` no `QUERYWORKORDERS`; `QUERYWORKORDERS` no bloco comum
  (`parse_text`/`add_text_filter` passaram para o bloco). Antigo e novo comparados
  com as mesmas entradas: mesmo SQL, binds e erros. 101 testes. Validado via MCP.
- 2026-11-03: `QUERYJOBPLANS` escrito (JOBPLAN + JOBTASK + JPASSETSPLINK), allowlist
  e testes. Instalado e validado via MCP; tarefas corrigidas (JOBTASK pelo dono).
  134 testes.
- 2026-11-04: filtro `location` do `QUERYJOBPLANS` validado (`L3T05M1` → 8);
  Itambé liga plano à location; dica na descrição do `assetnum` (allowlist).
- 2026-11-04: `QUERYWOSTATUS` escrito, instalado e validado via MCP; site explícito
  pelo índice `SITEID, CHANGEDATE, WONUM` (196 s → 4 s). 163 testes.

## Falta (ordem sugerida)

1. ~~Backlog de OS e reincidência de corretivas em `analysis/`.~~ Feitos em 2026-11-06 (branches
   `feat/analysis-backlog` e `feat/analysis-recurrence`). Homologação = base de teste (lixo do processo antigo);
   números reais só em produção. Sem data de corte do processo novo (usuário).
2. ~~Lentidão do `QUERYWORKORDERS`.~~ Encerrada (usuário, 2026-11-06: alguns
   segundos, não afeta). Sites explícitos no script (branch
   `perf/queryworkorders-explicit-sites`), recolado e conferido (total 18152).
3. ~~Tempo em status e consumo de material.~~ Feitos em 2026-11-06
   (`feat/analysis-status-time`, `feat/analysis-material`). `AMATER` confirmado.
   MTTR/paradas: pouco dado na homologação.
4. Primeiro agente: camadas 1-3 feitas em 2026-11-06 ([[agente-sem-chave-de-api]]).
   Falta testar no Claude Code com o subagente `analise-os` e, com a chave do
   Claude, rodar o grafo real e montar `tests/evals/`.
5. CLI `call_tool` no repo (sondas do scratchpad somem a cada sessão).
6. Pendências do usuário no Maximo: Log Level ERROR nos scripts. (Recolar
   `QUERYMATUSAGE.py` e schema e Description do `QUERYASSETDOWNTIME`: feitos,
   usuário, 2026-11-06.)
7. Linha DEBUG `implicit vars` do log do Manage. Só registro; não bloqueia nada.
8. Quando o guia da Itambé voltar: novos scripts/filtros/campos e `tests/evals/`.
9. Trocar a chave MAXADMIN por chave de gerente e testar com usuário **sem** acesso
   a um site (checklist do README do script).

## Riscos ativos

- Chave MAXADMIN em homologação: ver [[chave-api-por-usuario]].
- BMXAA10147E: voltou em 2026-10-29 com usuário em PT e sumiu com EN (2ª vez).
  Usuário da chave precisa estar em EN; afeta a chave por gerente. Ver
  [[chave-api-por-usuario]] e [[mas-mcp-server]].
- **MCP Server loga a `apikey` em texto puro (INFO).** Chave MAXADMIN de
  homologação exposta em 2026-10-29. Nova chave no `.env`; usuário **decidiu não
  revogar** a antiga (risco aceito: escrita total em homologação para quem lê os
  logs do pod). Mitigação necessária antes de chave de gerente. Ver
  [[mas-mcp-server]].
- Confirmado em runtime (2026-10-29): `SqlFormat.setTimestamp`, identidade do
  chamador via MCP, paginação com `getMbo(i)` (página 2). Não testado: páginas
  profundas (ex.: 700+) e desempenho.
