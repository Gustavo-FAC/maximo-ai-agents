# QUERYJOBPLANS

Consulta genérica de planos de trabalho (procedimentos padrão), somente leitura.
Publicada no MCP Server como automation script. Cobre "consultar_procedimentos":
cabeçalho do plano, tarefas em ordem (opção) e texto completo do procedimento
(campo opcional).

| Item | Valor |
|---|---|
| Script | `QUERYJOBPLANS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objetos | `JOBPLAN`; `JOBTASK` (com `include_tasks`); `JPASSETSPLINK` (filtros `assetnum`/`location`) |
| Arquivos | `QUERYJOBPLANS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_queryjobplans.py` (lógica pura, CPython) e `tests/unit/test_script_common.py` (bloco comum) |

## Descrição da ferramenta (colar no campo Description)

```text
Read-only job plan search: filters, asset links, tasks, words, paging, total.
```

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`
(= não informado). Descrições com até 100 caracteres; textos exatos em
[INSTALACAO.md](INSTALACAO.md).

| Variável | Descrição |
|---|---|
| `siteid` | Site IDs, comma-separated (max 20). Plans without site always included. |
| `jpnums` | Job plan numbers, comma-separated (max 50). |
| `status` | Job plan status values (max 20). Default: active only. ALL: every status. |
| `assetnum` | Asset numbers (max 20); job plans linked to these assets. |
| `location` | Location codes (max 20); job plans linked to these locations. |
| `persongroup` | Work group codes, comma-separated (max 20). |
| `templatetype` | Template types, comma-separated (max 20), e.g. MAINTENANCE. |
| `text` | Words that must all appear in the description (max 5 words, 100 chars). |
| `include_tasks` | Y to include the tasks of each job plan (default N; page_size max 50). |
| `fields` | Fields to return, comma-separated. jpnum, pluscrevnum, siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100); max 50 with tasks or long text. |

Nenhum filtro obrigatório: plano é cadastro, a resposta é limitada por `page_size` e
`total` é exato. Campos aceitos em `fields`: ver `FIELD_TYPES` no script.

## Decisões (usuário, 2026-11-03)

- **Tarefas sob pedido:** `include_tasks=Y` traz `tasks` em cada plano (JOBTASK,
  ordem de `jptask`). Os planos da página são reabertos por `jobplanid` e as
  tarefas lidas por relação temporária (`$QJPTASKS`, `jobplanid = :jobplanid`):
  JOBTASK aberto sem o JOBPLAN dono dá NullPointerException (`"parent" is null`,
  homologação 2026-11-03). Até 2000 tarefas por página; acima disso
  `tasks_truncated: true` e os planos seguintes vêm com `tasks: []`. Com tarefas,
  `page_size` máx 50.
- **Status padrão ACTIVE:** sem `status`, só revisões ativas, pelo valor interno
  (`synonymdomain`, `JOBPLANSTATUS`, `maxvalue = 'ACTIVE'`), o que cobre sinônimos do
  cliente. `status=ALL` desliga o filtro; outros valores filtram pelo valor gravado.
- **Ligação com ativo/local:** `assetnum` e `location` filtram pelos planos ligados em
  JPASSETSPLINK (por `jobplanid`, sem site na ligação). Plano usado só por PM (PM →
  `jpnum`) não aparece; se a Itambé ligar plano a ativo só pela PM, isso vira
  extensão. Na Itambé a ligação é pela **location** (2026-11-04): para planos de um
  ativo, o agente busca a location do ativo (`QUERYASSETS`) e filtra por ela (dica na
  descrição do `assetnum` na allowlist).
- **Texto do procedimento:** campo `description_longdescription` (até 32 mil
  caracteres, pode vir em rich text). Só vem quando pedido; com ele, `page_size` máx 50.

## Garantias do script

- Somente leitura: nenhuma chamada de `setValue`, `save` ou `changeStatus`.
  `MboSet` com flag `DISCARDABLE` e `cleanup()` em `finally`.
- Valores dos filtros só entram por bind (`SqlFormat.setObject`). Colunas vêm de
  listas fixas (`LIST_FILTERS`, `LINK_FILTERS`, `FIELD_TYPES`, `TASK_FIELDS`).
- `text`: cada palavra vira `upper(description) like :n` com `%palavra%` no bind.
- Limites validados no script: 50 jpnums, 20 valores por lista, 5 palavras,
  500 por página (50 com tarefas ou texto longo), 2000 tarefas por página.
- Identidade obrigatória; sem ela, erro `no_user`.
- Permissão READ no app JOBPLAN checada no código (APPLICATIONAUTH); sem ela,
  `not_authorized`. Sem variáveis `authapp`/`authsigoption`.
- **Sites:** plano com `siteid` só de site autorizado; plano sem site (nível
  organização) só de organização de algum site autorizado, ou de nível sistema (sem
  `orgid`). Filtro `siteid` inclui os planos sem site (valem para todos os sites).
- `count()` chamado uma vez para o `total`; tarefas lidas sem `count()`.

## Bloco comum

O trecho entre `# --- BEGIN COMMON` e `# --- END COMMON ---` é igual em todos os
scripts (decisão 2026-10-29: copiar, sem script biblioteca). Mudou em um, muda em
todos; `tests/unit/test_script_common.py` falha se divergir.

## Validar em homologação (antes de usar com gerente)

Validado em 2026-11-03 (Itambé, chave MAXADMIN): marcados com [x].

- [x] Ferramenta aparece no MCP com 12 parâmetros; nomes sem `u200b` (Title da MCP
      Tool veio com `u200b`, só cosmético; redigitar à mão).
- [x] Sem parâmetros: 2025 ACTIVE; `status=ALL` 2102. Itambé grava o sinônimo
      **ATIVO**; `status=ATIVO` dá os mesmos 2025 (filtro pelo valor interno ok).
- [x] Planos sem site: 203 (todos sem `orgid`, nível sistema, ex.: MONITORAR); entram
      com `siteid=FABRICA` (1895).
- [x] `jpnums` ESC0001,ESC0002 → `total` 2.
- [x] `include_tasks=Y` traz tarefas em ordem de `jptask`; plano sem tarefa
      (MONITORAR) → `tasks: []`; página de 50 ok. 1ª versão (JOBTASK sem dono) dava
      NullPointerException; corrigido e reinstalado.
- [x] `description_longdescription`: cerca de metade dos planos tem texto; vem com
      `<!-- RICH TEXT -->` e, nos vistos, só um código (ex.: `PS1486`). `page_size=100`
      com ele dá `out_of_range`.
- [x] `location` com plano ligado: `L3T05M1` → 8 planos (ex.: PTLUB80, PTMCA1,
      PTINV02) com `status=ALL` (2026-11-04).
- [ ] `assetnum` com plano ligado: a Itambé liga plano à **location**, não ao
      ativo. Os 3 ativos de `L3T05M1` (ACI0343, MCA5853, PEL0151) e CCM2.1,
      ACI0008, ACI0057, PEL0007 dão 0 planos. Mesma subconsulta do `location`
      (só muda a coluna); testar se aparecer ativo com ligação direta.
- [x] `text` ("motor" → 596), `unknown_field`, `invalid_flag`, `invalid_status`
      (`ALL,ACTIVE`), `invalid_text`, paginação (página 2) ok.
- [ ] Usuário sem READ no app JOBPLAN recebe `not_authorized`.
- [ ] Usuário **sem** acesso a um site não recebe planos desse site.
