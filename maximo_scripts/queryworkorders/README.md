# QUERYWORKORDERS

Consulta genérica de ordens de serviço (OS), somente leitura. Primeira ferramenta de
dados do agente de Análise de OS. Publicada no MCP Server como automation script.

| Item | Valor |
|---|---|
| Script | `QUERYWORKORDERS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `WORKORDER` (woclass WORKORDER e ACTIVITY, `istask = 0`) |
| Arquivos | `QUERYWORKORDERS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_queryworkorders.py` (lógica pura, CPython) |

## Descrição da ferramenta (colar no campo Description)

```text
Read-only search of work orders (WORKORDER, including activities, excluding tasks).
Returns work orders whose date_field falls between date_from and date_to (inclusive,
YYYY-MM-DD, max 366 days), with optional filters, pagination and field selection.
The date range may be omitted only when wonums is given (lookup by number).
The response always includes "total" (all matching records) so counts never need to
be estimated from a single page. Use it to list or retrieve work orders for analysis.
Do not use it for aggregated indicators over long periods; split the period instead.
List parameters accept comma-separated values. Use "*" for parameters not needed.
If the request is invalid, only an "error" object is returned with code and message.
```

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`
(= não informado). Descrições com até 100 caracteres (limite do Maximo); textos
exatos em [INSTALACAO.md](INSTALACAO.md).

| Variável | Obrigatória | Descrição (inglês, vai para o schema da ferramenta) |
|---|---|---|
| `date_from` | sim, exceto com `wonums` | Start date, YYYY-MM-DD, inclusive. Required unless wonums is given. |
| `date_to` | sim, exceto com `wonums` | End date, YYYY-MM-DD, inclusive. Max 366 days after date_from. Required unless wonums is given. |
| `date_field` | não | Date attribute for the range: reportdate (default), statusdate, targstartdate, targcompdate, schedstart, schedfinish, actstart, actfinish. |
| `siteid` | não | Site IDs, comma-separated (max 20). |
| `wonums` | não | Work order numbers, comma-separated (max 50). Dates optional when given. |
| `status` | não | Status values, comma-separated (max 20), e.g. APPR,INPRG,COMP. |
| `priority` | não | Priority integers, comma-separated (max 20). |
| `assetnum` | não | Asset numbers, comma-separated (max 20). |
| `location` | não | Location codes, comma-separated (max 20). |
| `persongroup` | não | Crew/person group codes, comma-separated (max 20). |
| `worktype` | não | Work types, comma-separated (max 20), e.g. PM,CM,EM. |
| `fields` | não | Fields to return, comma-separated. Default: wonum, siteid, description, status, worktype, wopriority, assetnum, location, persongroup, reportdate, actstart, actfinish. wonum and siteid are always included. |
| `page` | não | Page number, starting at 1 (default 1). |
| `page_size` | não | Items per page, 1 to 500 (default 100). |

Campos aceitos em `fields`: ver `FIELD_TYPES` no script.

## Registro no Maximo

Passo a passo campo a campo em [INSTALACAO.md](INSTALACAO.md).

## Garantias do script

- Somente leitura: nenhuma chamada de `setValue`, `save` ou `changeStatus`.
  `MboSet` com flag `DISCARDABLE` e `cleanup()` em `finally`.
- Valores dos filtros só entram por bind (`SqlFormat.setObject`/`setTimestamp`).
  Colunas vêm de listas fixas (`DATE_FIELDS`, `LIST_FILTERS`, `FIELD_TYPES`).
- Limites validados no script: 366 dias, 50 wonum, 20 valores por lista, 500 por
  página.
- Identidade obrigatória (`request.getUserInfo()`); sem ela, erro `no_user`.
- Permissão READ em WOTRACK checada no código (APPLICATIONAUTH); sem ela, erro
  `not_authorized`. **Não usar variáveis `authapp`/`authsigoption`**: toda variável
  vira parâmetro da ferramenta e o chamador poderia sobrescrever (visto no OAS em
  2026-10-22).
- Filtro de sites autorizados ao usuário (`SITEAUTH`/`MAXGROUP.authallsites`)
  sempre aplicado, além da segurança do próprio Maximo.
- `count()` chamado uma vez para o `total`.

## Validar em homologação (antes de usar com gerente)

- [x] Toda variável vira parâmetro; nenhum parâmetro é obrigatório no schema;
      tudo `string`; Description (≤100) vira a descrição da ferramenta. (OAS 2026-10-22)
- [ ] Ferramenta aparece no MCP com 14 parâmetros, sem caracteres invisíveis.
- [ ] Parâmetro omitido usa o padrão `*` (ou o schema obriga todos?).
- [ ] Origem dos parâmetros (log `param sources`: variable, body ou query).
- [ ] `request.getUserInfo()` existe no caminho MCP e é o dono da `apikey`.
- [ ] `SqlFormat.setTimestamp` aceito; intervalo de datas correto no SQL
      (logger `autoscript` em DEBUG).
- [ ] Usuário **sem** acesso a um site não recebe OS desse site.
- [ ] Usuário sem permissão READ em WOTRACK recebe `not_authorized`.
- [ ] Página profunda (ex.: página 50 de 100) com tempo aceitável.
- [ ] Valores com acento (ex.: equipe) funcionam.
