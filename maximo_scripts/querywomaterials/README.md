# QUERYWOMATERIALS

Materiais planejados nas OS, somente leitura. Uma linha por material planejado
(WPMATERIAL): OS, site, tarefa, item, descrição, quantidade, unidade, custo, almoxarifado,
tipo de linha, emissão direta e data necessária. Com `include_balance=Y`, cada linha traz o
saldo atual do item no almoxarifado planejado (INVBALANCES). Publicada no MCP Server como
automation script.

| Item | Valor |
|---|---|
| Script | `QUERYWOMATERIALS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `WPMATERIAL` (+ `INVBALANCES` sob pedido) |
| Permissão | READ em `WOTRACK`; com `include_balance`, também READ em `INVENTOR` |
| Arquivos | `QUERYWOMATERIALS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_querywomaterials.py` e `tests/unit/test_script_common.py` |

Decisão do usuário (2026-11-04): material em **2 scripts**: este (planejado + saldo) e
`QUERYMATUSAGE` (consumo real, MATUSETRANS). Datas pela OS.

**Fora dos agentes** (`DORMANT_TOOLS` na allowlist, 2026-11-04): a Itambé não planeja
material no Maximo (WPMATERIAL vazio). Volta para `AGENT_TOOLS` quando um cliente usar.

## Para que serve

- "O material da OS está disponível?": `wonums` + `include_balance=Y`.
- Materiais planejados das OS programadas na semana: `date_field=schedstart`.
- Itens mais planejados, custo planejado por ativo/tipo de trabalho: **conta em
  `analysis/`**, não pelo LLM.

## Como liga material e OS

- Linha planejada em tarefa tem o `wonum` da tarefa e `taskid`. Datas, `wonums` e filtros
  da OS valem para a **OS-topo**: `t.wogroup` (tarefa → OS-mãe; OS sem ser tarefa →
  ela mesma). Assim `wonums` traz também as linhas das tarefas.
- Só OS e atividades (`woclass` WORKORDER/ACTIVITY), como no `QUERYWORKORDERS`.
- `location` na resposta é o **almoxarifado** da linha (atributo do Maximo). O parâmetro
  `location` filtra a location da OS; o almoxarifado é `storeloc`.

## Saldo (`include_balance=Y`)

- Chave: `itemnum` + almoxarifado (`location`) + site do almoxarifado (`storelocsite`,
  ou o site da linha se vazio). Uma consulta INVBALANCES por página, com bind por chave.
- `balance`: `null` sem almoxarifado (emissão direta, item fora de estoque);
  `{"total": 0.0, "bins": []}` se o item não tem saldo naquele almoxarifado; senão
  `total` (soma de `curbal`, feita pelo script) e `bins` (`binnum`, `lotnum`,
  `conditioncode`, `curbal`).
- Saldo atual, não descontado de reservas (INVRESERVE). Disponibilidade líquida fica para
  depois, se o consultor pedir.
- `page_size` máx 50; até 2000 linhas de saldo por página (`balances_truncated`).

## Descrição da ferramenta (digitar no campo Description)

```text
Read-only planned materials of work orders: date range (YYYY-MM-DD) or wonums, filters, paging, total.
```

A descrição completa para o LLM fica na allowlist (`QUERY_WO_MATERIALS`).

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`.
Textos exatos em [INSTALACAO.md](INSTALACAO.md).

| Variável | Obrigatória | Filtra |
|---|---|---|
| `date_from` | sim, exceto com `wonums` | data da OS-topo `>=` início do dia |
| `date_to` | sim, exceto com `wonums` | `<` dia seguinte (inclusivo); máx 366 dias |
| `date_field` | não | `reportdate` (padrão), `statusdate`, `targstartdate`, `targcompdate`, `schedstart`, `schedfinish`, `actstart`, `actfinish` |
| `siteid` | não | `WPMATERIAL.siteid` |
| `wonums` | não | OS-topo (máx 50); dispensa as datas |
| `status`, `assetnum`, `location`, `persongroup`, `worktype` | não | campos da OS-topo |
| `itemnums` | não | `itemnum` (máx 50) |
| `storeloc` | não | almoxarifado (`WPMATERIAL.location`) |
| `include_balance` | não | `Y` traz o saldo |
| `fields` | não | Padrão `wonum, siteid, taskid, itemnum, description, itemqty, orderunit, unitcost, linecost, location, storelocsite, linetype, directreq, requiredate`; também `restype`, `orgid`, `itemsetid`, `vendor`, `conditioncode`, `issueto`, `requestby`, `requestnum`, `wpitemid` |
| `page` | não | Página, a partir de 1 |
| `page_size` | não | 1 a 500 (padrão 100); máx 50 com saldo |

Ordem: `wonum, siteid, wpitemid`.

## Colunas

Do `apischema` `MXAPIWODETAIL` (`nested`, filho `wpmaterial`, 2026-11-04). O filho não
mostra `wonum`/`siteid` (chave de ligação com a OS); confirmar na 1ª chamada.
`issueunit` e `mrnum` não aparecem (por isso fora). Campos próprios da Itambé
(`sanum` = solicitação do Protheus, `justificativa`, `prioridade`, `wpm1` a `wpm6`)
ficam de fora (regra: só atributos padrão).

## Garantias do script

- Somente leitura: `MboSet` `DISCARDABLE`, `cleanup()` em `finally`, nenhuma escrita.
- Valores só por bind; colunas de listas fixas (`LIST_FILTERS`, `WO_FILTERS`,
  `DATE_FIELDS`, `FIELD_TYPES`).
- Limites: 366 dias, 50 OS, 50 itens, 20 valores por lista, 500 por página (50 com saldo),
  2000 linhas de saldo.
- Identidade obrigatória; WOTRACK/READ checado; INVENTOR/READ checado só com saldo;
  sites autorizados sempre aplicados (também na consulta de saldo).
- **Site explícito**: sem `siteid`, `siteid in (sites autorizados)`.
- `count()` uma vez para o `total` (= linhas planejadas).

## Bloco comum

Copiado do `QUERYASSETS` sem mudança. `authorized_sites_query`/`read_authorized_sites`
repetidas do `QUERYWOSTATUS`; `parse_flag`/`bind_placeholders` do `QUERYJOBPLANS` (fora
do bloco comum, para não reinstalar os outros).

## Validar em homologação

2026-11-04: instalado; **WPMATERIAL vazio em homologação** (nenhuma OS com material
planejado). Conferidos: 16 parâmetros sem `u200b`; erros `required`,
`invalid_date_field`, `range_too_large`, `out_of_range` (saldo + 51), `unknown_field`;
filtros combinados sem erro (`total` 0). Itens com dados ficam para quando houver
material planejado.

- [x] 16 parâmetros, sem `u200b`.
- [ ] `wonums` de OS com material planejado → linhas; com tarefa, `taskid` preenchido e
      `wonum` da tarefa (confirma a ligação por `wogroup`).
- [ ] Período (`reportdate`, 1 mês) → `total`; tempo em 1 mês e 366 dias.
- [ ] `include_balance=Y` → `balance` com `total`/`bins`; linha de emissão direta com `null`.
- [ ] `storeloc`, `itemnums`, `status`, `worktype` filtram certo.
- [ ] Todos os campos de `fields` existem (sem `internal_error`).
- [x] Erros: sem `date_to` → `required`; `date_field=x` → `invalid_date_field`;
      `include_balance=Y` + `page_size=51` → `out_of_range`.
- [ ] Usuário sem INVENTOR/READ com `include_balance=Y` → `not_authorized`.
