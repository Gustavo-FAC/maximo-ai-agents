# QUERYPMS

Consulta genérica de preventivas (registros de PM: o cadastro que gera OS de
preventiva por frequência), somente leitura. Cobre as perguntas 1 a 3 do guia da
Itambé (`memoria/wiki/sources/guia-levantamento-fase1.md`): MPs vencendo no período,
se existe MP para um ativo ou posição, e a última MP gerada.

| Item | Valor |
|---|---|
| Script | `QUERYPMS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `PM` |
| Permissão | READ no app `PM` (checada no código) |
| Arquivos | `QUERYPMS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_querypms.py` e `tests/unit/test_script_common.py` (bloco comum) |

## Descrição da ferramenta (colar no campo Description)

```text
Read-only PM search: due date range, asset, location, filters, paging, total.
```

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`
(= não informado). Descrições com até 100 caracteres.

| Variável | Descrição |
|---|---|
| `due_from` | Earliest due date (extdate or nextdate), YYYY-MM-DD, inclusive. Optional. |
| `due_to` | Latest due date, YYYY-MM-DD, inclusive. Optional; alone: everything due up to it. |
| `siteid` | Site IDs, comma-separated (max 20). |
| `pmnums` | PM numbers, comma-separated (max 50). |
| `status` | PM status values (max 20). Default: active only. ALL: every status. |
| `assetnum` | Asset numbers, comma-separated (max 20). |
| `location` | Location codes, comma-separated (max 20). |
| `jpnum` | Job plan numbers, comma-separated (max 20). |
| `worktype` | Work types, comma-separated (max 20). |
| `crewid` | Crew IDs, comma-separated (max 20). |
| `persongroup` | Person group (work group) codes, comma-separated (max 20). |
| `text` | Words that must all appear in the description (max 5 words, 100 chars). |
| `fields` | Fields to return, comma-separated. pmnum and siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100); max 50 with long description. |

Campos aceitos em `fields`: ver `FIELD_TYPES` no script.

## Comportamento

- **Cadastro:** nenhum filtro obrigatório (sem intervalo de datas); a página limita a
  resposta e `total` é exato.
- **Status padrão:** só PMs ativas, pelo valor interno (`synonymdomain` PMSTATUS =
  ACTIVE), o que cobre sinônimos do cliente. `status=ALL` desliga o filtro.
- **Vencimento:** `due_from` e `due_to` são opcionais e independentes e valem para
  `coalesce(extdate, nextdate)` (data estendida, quando preenchida, substitui a
  próxima data, como no Maximo). Só `due_to` = tudo que vence até o dia (ex.: PMs
  vencidas = ontem). Cada item traz `due_date` quando `nextdate` e `extdate` vêm na
  resposta (padrão).
- **Ordem:** `nextdate, pmnum, siteid`.
- **Site sempre explícito** (lição do `QUERYWOSTATUS`): sem `siteid`, o script lê os
  sites autorizados do usuário e põe `siteid in (...)`.
- **Campo do cliente** `modalidade` (Itambé): aceito em `fields` só se o atributo
  existe neste Maximo (dicionário de dados, em tempo de execução); senão
  `unknown_field`. Nunca no padrão. Mesma regra no `QUERYWORKORDERS`.
- **OS geradas pela PM:** `script_queryworkorders` com `pmnum` (filtro e campo).
- Fora por enquanto: PM por medidor (PMMETER), sequência de planos (PMSEQUENCE),
  previsão (PMFORECAST). PM de rota: o filtro `assetnum`/`location` vê só o ativo e
  a location da PM, não as paradas da rota.

## Garantias do script

- Somente leitura: nenhuma chamada de `setValue`, `save` ou `changeStatus`.
  `MboSet` com flag `DISCARDABLE` e `cleanup()` em `finally`.
- Valores dos filtros só por bind (`SqlFormat`); colunas de listas fixas
  (`LIST_FILTERS`, `FIELD_TYPES`).
- Identidade obrigatória; permissão READ em PM checada no código; filtro de sites
  autorizados sempre aplicado. **Não usar variáveis `authapp`/`authsigoption`.**
- Bloco comum idêntico aos outros scripts (`tests/unit/test_script_common.py`).

## Validar em homologação

- [ ] Ferramenta aparece no MCP com 15 parâmetros, sem caracteres invisíveis.
- [ ] Sem filtros: `total` de PMs ativas, `filters.status = ["ACTIVE"]`.
- [ ] `due_from`/`due_to` da semana: só PMs com `due_date` no intervalo.
- [ ] Só `due_to` = ontem: PMs vencidas.
- [ ] `assetnum` e `location` de um ativo/posição com PM conhecida.
- [ ] `fields=modalidade`: valor preenchido (Itambé).
- [ ] `status=ALL,ACTIVE` → `invalid_status`; `due_to` antes de `due_from` →
      `invalid_range`.
- [ ] Usuário sem READ em PM recebe `not_authorized`.
