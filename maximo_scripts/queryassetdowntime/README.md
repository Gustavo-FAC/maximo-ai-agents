# QUERYASSETDOWNTIME

Histórico de paradas de ativo, somente leitura. Uma linha por mudança de estado
(ASSETSTATUS): ativo, site, data, parado/funcionando, horas de parada, código de
parada, operacional, OS, location e quem registrou. Publicada no MCP Server como
automation script.

| Item | Valor |
|---|---|
| Script | `QUERYASSETDOWNTIME` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `ASSETSTATUS` |
| Permissão | READ em `ASSET` (checada no código, como no `QUERYASSETS`) |
| Arquivos | `QUERYASSETDOWNTIME.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_queryassetdowntime.py` (lógica pura, CPython) e `tests/unit/test_script_common.py` (bloco comum) |

Decisão do usuário (2026-11-04): histórico em **2 scripts novos**; este é o 2º,
depois do `QUERYWOSTATUS`.

## Para que serve

- Histórico completo de paradas de um ou mais ativos: `assetnums` sem datas.
- Paradas num período: por site, location, código de parada, OS, quem registrou;
  só as quedas (`event=down`) ou só os retornos (`event=up`).
- Horas paradas, MTTR, MTBF, disponibilidade: **a conta é feita em `analysis/`**,
  não pelo LLM; a ferramenta só entrega as mudanças em ordem cronológica por ativo.

Como o Maximo grava (confirmado em homologação, 2026-11-04): cada queda gera uma
linha com `isrunning` falso e `downtime` 0; o retorno gera outra com `isrunning`
verdadeiro e `downtime` = horas paradas. Com intervalo de datas, uma queda antes de
`date_from` cujo retorno cai dentro do período vem só com o retorno. Para horas exatas
no período, buscar o histórico do ativo por `assetnums`.

Cuidados para o `analysis/` (vistos nos dados da Itambé):

- `downtime` é o valor gravado, nem sempre a diferença entre as datas: MCC2213
  caiu 08:00 e voltou 10:56 com `downtime` 2.0 (ACI1020: 21:10 → 21:50, 0.667, bate).
- Pares repetidos: ACI1020 tem 5 quedas e 5 retornos idênticos (mesma data, mesma OS,
  `assetstatusid` 10071 a 10080). Deduplicar antes de somar.
- Linha inicial sem queda antes: ACI1020 tem `isrunning` verdadeiro em 2009 com
  `downtime` 0 (registro de cadastro).
- Homologação quase não usa ASSETSTATUS: ~120 linhas, 4 em 2025, 0 em 2026. Antes de
  prometer indicadores de parada, confirmar com o consultor se a Itambé registra
  paradas no Maximo em produção.

## Descrição da ferramenta (digitar no campo Description)

```text
Read-only asset downtime history: date range (YYYY-MM-DD) or assetnums, filters, paging, total.
```

O MCP usa esse campo como descrição da ferramenta. A descrição completa para o LLM fica
na allowlist (`src/maximo_agents/mcp/allowlist.py`, `QUERY_ASSET_DOWNTIME`).

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`
(= não informado). Textos exatos (até 100 caracteres) em [INSTALACAO.md](INSTALACAO.md).

| Variável | Obrigatória | Filtra |
|---|---|---|
| `date_from` | sim, exceto com `assetnums`/`wonums` | `ASSETSTATUS.changedate >=` início do dia |
| `date_to` | sim, exceto com `assetnums`/`wonums` | `changedate <` dia seguinte (inclusivo); máx 366 dias |
| `siteid` | não | `siteid` |
| `assetnums` | não | `assetnum` (máx 50); dispensa as datas |
| `location` | não | `location` gravada na mudança |
| `wonums` | não | `wonum` gravada na mudança (máx 50); dispensa as datas |
| `code` | não | `code` (código de parada) |
| `event` | não | `down` → `isrunning = 0`; `up` → `isrunning = 1` (SQL fixo, sem bind) |
| `changeby` | não | `changeby` |
| `fields` | não | Padrão `assetnum, siteid, changedate, isrunning, downtime, code, operational, wonum, location, changeby`; também `orgid`, `assetstatusid`, `calnum` |
| `page` | não | Página, a partir de 1 |
| `page_size` | não | 1 a 500 (padrão 100) |

Ordem: `assetnum, siteid, changedate, assetstatusid` (histórico de cada ativo, mais
antigo primeiro).

## Colunas

Do `apischema` de `MXAPIASSETSTATUS` (homologação, 2026-11-04): `assetnum`,
`assetstatusid`, `calnum`, `changeby`, `changedate`, `code`, `downtime` (number),
`isrunning` (boolean, "Up"), `location`, `operational` (boolean), `orgid`, `siteid`,
`wonum`. `MXASSETSTATUS` dá HTTP 500 `mosInfo`.

## Garantias do script

- Somente leitura: nenhuma chamada de escrita (não é o `REPORTDOWNTIME`). `MboSet`
  `DISCARDABLE`, `cleanup()` em `finally`.
- Valores só por bind (`SqlFormat`); colunas de listas fixas (`LIST_FILTERS`,
  `FIELD_TYPES`, `EVENT_WHERE`).
- Limites: 366 dias, 50 ativos, 50 OS, 20 valores por lista, 500 por página.
- Identidade obrigatória; permissão READ em ASSET checada no código; filtro de sites
  autorizados sempre aplicado.
- **Site sempre explícito** (lição do `QUERYWOSTATUS`): sem `siteid`, o script lê os
  sites autorizados do usuário e põe `siteid in (...)`. Sem site autorizado:
  `not_authorized`.
- `count()` uma vez para o `total` (= número de mudanças).

## Bloco comum

Trecho entre `# --- BEGIN COMMON` e `# --- END COMMON ---` copiado do
`QUERYWORKORDERS` sem mudança. `tests/unit/test_script_common.py` falha se divergir.
`authorized_sites_query` e `read_authorized_sites` estão repetidas do `QUERYWOSTATUS`
(fora do bloco comum, para não reinstalar os outros scripts).

## Validar em homologação

1ª instalação em 2026-11-04 (cliente avulso pelo SDK MCP).

- [x] 12 parâmetros, sem `u200b`. Description veio com `YYYY-NN-DD` (digitação):
      corrigir para `YYYY-MM-DD`.
- [x] Período com paradas → `total`; `downtime` preenchido nas linhas com
      `isrunning` verdadeiro (2020: 4; 2023: 10; 2025: 4; 2026: 0).
- [x] `assetnums` sem datas → histórico completo em ordem (14 linhas de 3 ativos).
- [x] `event=up`, `event=down`, `code`, `location`, `wonums` filtram certo; paginação ok.
- [x] Sem `date_to` → `required`; 367 dias → `range_too_large`; `event=x` →
      `invalid_event`; `unknown_field`.
- [x] Campos `orgid`, `assetstatusid`, `calnum` existem (`calnum` nulo).
- [x] Tempo: 366 dias sem `siteid` cerca de 2 s (tabela pequena). Índices da
      ASSETSTATUS não levantados (não foi preciso).
- [ ] Usuário sem READ em ASSET recebe `not_authorized`.
