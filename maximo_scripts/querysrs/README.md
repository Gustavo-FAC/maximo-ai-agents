# QUERYSRS

Consulta genérica de solicitações de serviço (SR, "SS"), somente leitura. Cobre as
perguntas 13 e 14 do guia da Itambé (`memoria/wiki/sources/guia-levantamento-fase1.md`):
SS pendentes por grupo proprietário e status/tratativa de uma SS. Consultor
(2026-11-18): app de SR **padrão** do Maximo (e Mobile), grupo proprietário =
`ownergroup`. Manutenção externa (perguntas 15 a 17) fica para um 2º passo: o
fornecedor está na **ordem de compra** (cadastro em Empresas).

| Item | Valor |
|---|---|
| Script | `QUERYSRS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `SR` (TICKET, classe SR) |
| Permissão | READ no app `SR` (checada no código) |
| Arquivos | `QUERYSRS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_querysrs.py` e `tests/unit/test_script_common.py` (bloco comum) |

## Descrição da ferramenta (colar no campo Description)

```text
Read-only service request (SR) search: date range or ticketids, filters, paging, total.
```

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`
(= não informado). Descrições com até 100 caracteres.

| Variável | Descrição |
|---|---|
| `date_from` | Start date, YYYY-MM-DD, inclusive. Required unless ticketids is given. |
| `date_to` | End date, YYYY-MM-DD, inclusive. Max 366 days after date_from. |
| `date_field` | Range date: reportdate (default), statusdate, targetstart, targetfinish, actualfinish |
| `siteid` | Site IDs, comma-separated (max 20). |
| `ticketids` | Service request numbers, comma-separated (max 50). Dates optional when given. |
| `status` | Status values, comma-separated (max 20). |
| `ownergroup` | Owner group codes (team responsible), comma-separated (max 20). |
| `owner` | Owner person IDs, comma-separated (max 20). |
| `reportedby` | Person IDs who reported the request, comma-separated (max 20). |
| `priority` | Reported priority integers, comma-separated (max 20). |
| `assetnum` | Asset numbers, comma-separated (max 20). |
| `location` | Location codes, comma-separated (max 20). |
| `text` | Words that must all appear in the description (max 5 words, 100 chars). |
| `include_workorders` | Y returns the work orders created from each request. Default N; max 50/page. |
| `include_history` | Y returns each request's status changes. Default N; max 50/page. |
| `fields` | Fields to return, comma-separated. ticketid and siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100). |

`date_field` também aceita `actualstart` e `changedate` (não cabem na descrição; se o
valor for inválido, o erro lista todos). Campos aceitos em `fields`: `FIELD_TYPES` no
script.

## Garantias do script

- Somente leitura; `MboSet` com `DISCARDABLE` e `cleanup()` em `finally`.
- Valores só por bind; colunas de listas fixas (`LIST_FILTERS`, `FIELD_TYPES`).
- Intervalo de datas obrigatório (movimento), até 366 dias; dispensado só com
  `ticketids` (máx 50).
- Permissão READ no app `SR` checada no código; sites autorizados sempre aplicados.
  Sem `siteid`, os sites autorizados entram explícitos (`siteid in (...)`, lição do
  `QUERYWORKORDERS`). **SR sem site não volta** (autorização por site; conferir na
  homologação se a Itambé cria SR sem site).
- `class in (sinônimos de SR)` repetido como salvaguarda (o objeto SR já filtra).
- `include_workorders=Y`: OS com `origrecordclass` = classe SR e `origrecordid` = SR
  da página, também com filtro de sites autorizados; até 500 por chamada
  (`workorders_truncated`). Consulta própria no WORKORDER (não relação), para aplicar
  a autorização por site.
- `include_history=Y`: TKSTATUS lido pela SR dona (relação ad hoc `$QSRSTATUS`, lição
  do JOBTASK); até 3000 mudanças por chamada (`history_truncated`); `ticketuid` volta
  junto. Campos do histórico conferidos no dicionário de dados (`getMaximoDD`): a
  TKSTATUS da Itambé não tem `OWNER` (BMXAA4176E em 2026-11-19); só os existentes voltam.
- `ownergroup` (campo e filtro) lê o primeiro atributo existente em
  `OWNERGROUP_ATTRIBUTES` = (`itcownergroup`, `ownergroup`), conferido no dicionário de
  dados. A Itambé guarda o grupo no campo próprio `ITCOWNERGROUP` (para o status não ir
  sozinho a QUEUED) e deixa `OWNERGROUP` vazio. O nome na resposta continua
  `ownergroup`. O histórico (TKSTATUS) só tem o `ownergroup` padrão.
- Descrição longa, OS ou histórico: página de até 50.

## Bloco comum

Trecho entre `# --- BEGIN COMMON` e `# --- END COMMON ---` igual ao do `QUERYASSETS`.
`tests/unit/test_script_common.py` falha se divergir.

## Validar em homologação

- [x] Ferramenta aparece no MCP com 18 parâmetros (2026-11-19, `script_querysrs`).
- [ ] Um ano por `reportdate`: `total` coerente com o app SR (filtro de site igual).
      Homologação quase sem SR: 54 desde abr/2026 (testes), nenhuma mai/2025–abr/2026.
- [x] Status em uso e grupos vistos nos dados (2026-11-19). Fluxo: NOVO → AGAPROV →
      EMAND → SOLUC → FECHADO, ou CANCELADO. Grupos (`itcownergroup`): DEM-PCM,
      DEE-PCM, DRB-PCM, DPROD-PCM, DPROD-CL. Filtro `ownergroup=dem-pcm` +
      `status=AGAPROV,EMAND,NOVO` = 27, igual à contagem à mão.
- [x] `ticketids` sem datas acha a SR; `include_workorders=Y` traz as OS geradas
      (SR 10200 → OS 1632462, 2026-11-19); limite de 366 dias dá `range_too_large`.
- [x] `include_history=Y` (2026-11-19, após corrigir BMXAA4176E): SR 10200 traz
      NOVO, AGAPROV, EMAND, SOLUC ("Concluído pelo Mobile"), FECHADO. A TKSTATUS da
      Itambé só tem `status`, `changedate`, `changeby`, `memo` (sem owner/ownergroup).
- [ ] SR sem site existe na Itambé? (Se sim, decidir regra.)
- [ ] Usuário sem READ no app SR recebe `not_authorized`.
