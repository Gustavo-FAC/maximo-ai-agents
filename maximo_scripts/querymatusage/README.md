# QUERYMATUSAGE

Consumo real de material, somente leitura. Uma linha por baixa ou devolução de item do
almoxarifado (MATUSETRANS): OS (`refwo`), site, data, tipo (ISSUE/RETURN), item,
descrição, quantidade, unidade, custo, almoxarifado, ativo, location e para quem foi.
Publicada no MCP Server como automation script.

| Item | Valor |
|---|---|
| Script | `QUERYMATUSAGE` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `MATUSETRANS` |
| Permissão | READ em `WOTRACK` (checada no código) |
| Arquivos | `QUERYMATUSAGE.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_querymatusage.py` e `tests/unit/test_script_common.py` |

Decisão do usuário (2026-11-04): material em **2 scripts**; este é o consumo real, o
`QUERYWOMATERIALS` é o planejado (com saldo).

## Para que serve

- Material gasto numa OS (e nas tarefas dela): `wonums`.
- Consumo por ativo, location, item ou almoxarifado num período.
- Consumo em corretivas: `worktype=CO`.
- Custo de material por ativo, itens mais consumidos, planejado x realizado: **conta em
  `analysis/`**, não pelo LLM.

## Sinal e devoluções

- Sinais (conferidos em homologação, 2026-11-04): `quantity` **negativo na baixa (ISSUE),
  positivo na devolução (RETURN)**; `linecost` **ao contrário** (positivo na baixa,
  negativo na devolução). Consumo e custo líquidos = soma, feita por código.
  `positivequantity` é a quantidade sem sinal.
- Devolução pode apontar a baixa original em `issueid` (na Itambé veio vazio);
  `qtyreturned` na baixa diz quanto voltou.
- `issuetype=issue|return` filtra pelo valor interno (`synonymdomain` ISSUETYP), com SQL
  fixo. Na resposta vem o valor externo da Itambé (`EMISSÃO`, `RETORNAR`).

## Como liga consumo e OS

- `refwo` é a OS; `tositeid` é o site da OS; `siteid` é o site do almoxarifado.
- Sem `wonums`, `worktype` ou `persongroup`, entram também baixas **sem OS** (para ativo,
  location ou conta).
- Com eles, subconsulta na OS-topo por `wogroup` (como no `QUERYWOMATERIALS`): `wonums`
  traz também o consumo das tarefas; baixas sem OS saem.
- Datas são da própria transação (`actualdate`, padrão, ou `transdate`), não da OS.

## Descrição da ferramenta (digitar no campo Description)

```text
Read-only material usage (issues and returns): date range (YYYY-MM-DD) or wonums, filters, paging, total.
```

A descrição completa para o LLM fica na allowlist (`QUERY_MAT_USAGE`).

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`.
Textos exatos em [INSTALACAO.md](INSTALACAO.md).

| Variável | Obrigatória | Filtra |
|---|---|---|
| `date_from` | sim, exceto com `wonums` | `date_field >=` início do dia |
| `date_to` | sim, exceto com `wonums` | `<` dia seguinte (inclusivo); máx 366 dias |
| `date_field` | não | `actualdate` (padrão) ou `transdate` |
| `siteid` | não | `siteid` (site do almoxarifado) |
| `wonums` | não | OS-topo (máx 50); dispensa as datas |
| `itemnums` | não | `itemnum` (máx 50) |
| `storeloc` | não | `storeloc` |
| `assetnum` | não | `assetnum` da transação |
| `location` | não | `location` da transação |
| `issuetype` | não | `issue` ou `return` |
| `worktype`, `persongroup` | não | campos da OS-topo |
| `fields` | não | Padrão `refwo, siteid, matusetransid, actualdate, issuetype, itemnum, description, quantity, issueunit, unitcost, linecost, storeloc, assetnum, location, issueto`; outros na allowlist |
| `page` | não | Página, a partir de 1 |
| `page_size` | não | 1 a 500 (padrão 100) |

Ordem: `date_field, matusetransid` (mais antigo primeiro).

## Colunas

Do `apischema` `MXAPIWODETAIL` (`nested`, filho `matusetrans`, 2026-11-04): `refwo`,
`siteid`, `tositeid`, `itemnum`, `quantity`, `positivequantity`, `qtyreturned`,
`issueid`, `unitcost`, `linecost`, `actualcost`, `transdate`, `actualdate`, `issuetype`,
`storeloc`, `binnum`, `assetnum`, `location`, `issueto`, `enterby`, `matusetransid`,
`taskid`, `actualstaskid` etc. Campos próprios (`it1` a `it10`, `itin1` a `itin7`) fora.

## Garantias do script

- Somente leitura: `MboSet` `DISCARDABLE`, `cleanup()` em `finally`, nenhuma escrita.
- Valores só por bind; colunas de listas fixas; `issuetype` com SQL fixo (`ISSUE_TYPE_WHERE`).
- Limites: 366 dias, 50 OS, 50 itens, 20 valores por lista, 500 por página.
- Identidade obrigatória; WOTRACK/READ checado; sites autorizados sempre aplicados.
- **Site explícito**: sem `siteid`, `siteid in (sites autorizados)`.
- `count()` uma vez para o `total` (= transações).

## Bloco comum

Copiado do `QUERYASSETS` sem mudança. Funções de site e `bind_placeholders` repetidas de
outros scripts, fora do bloco comum.

## Validar em homologação (2026-11-04, via MCP)

- [x] 15 parâmetros, sem `u200b`.
- [x] 366 dias → 5241 transações em 0,4 s (dados até jun/2026).
- [x] Sinal de `quantity`/`linecost` em ISSUE e RETURN (opostos; ver acima).
- [x] `wonums=1116802` sem datas → 109 linhas (ligação por `wogroup` ok). Sem caso
      de consumo em tarefa.
- [x] `issuetype=issue`/`return` (5011 + 230 = 5241), `worktype=CO` (202).
- [ ] `assetnum`, `storeloc` como filtro (mesmo código das listas; sem caso testado).
- [x] Todos os campos de `fields` existem (sem `internal_error`).
- [x] Erros: `required`, `invalid_issuetype`, `invalid_date_field`.
