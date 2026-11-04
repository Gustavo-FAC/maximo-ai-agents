# QUERYWOSTATUS

Histórico de mudanças de status de ordens de serviço (OS), somente leitura. Uma
linha por mudança (WOSTATUS): OS, site, status novo, data, quem mudou e observação.
Publicada no MCP Server como automation script.

| Item | Valor |
|---|---|
| Script | `QUERYWOSTATUS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `WOSTATUS`, só de OS com woclass WORKORDER e ACTIVITY e `istask = 0` (mesmo escopo do `QUERYWORKORDERS`) |
| Arquivos | `QUERYWOSTATUS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_querywostatus.py` (lógica pura, CPython) e `tests/unit/test_script_common.py` (bloco comum) |

Decisão do usuário (2026-11-04): histórico de status em **2 scripts novos**, não como
opção das ferramentas atuais (as perguntas cruzam muitos registros por período).
Primeiro este; depois `QUERYASSETDOWNTIME` (ASSETSTATUS, paradas de ativo).

## Para que serve

- Histórico completo de uma ou mais OS: `wonums` sem datas.
- Mudanças num período: quais OS foram para um status (ex.: aguardando material),
  quem mudou, por ativo, location, equipe ou tipo de trabalho.
- Tempo em cada status = diferença entre mudanças seguidas da mesma OS. **A conta é
  feita em `analysis/`**, não pelo LLM; a ferramenta só entrega as mudanças em
  ordem cronológica por OS.

Com intervalo de datas, mudanças fora dele não vêm: o primeiro status de uma OS no
período pode ter começado antes. Para tempo em status, buscar o histórico completo
das OS por `wonums`.

## Descrição da ferramenta (colar no campo Description)

```text
Read-only work order status history: date range (YYYY-MM-DD) or wonums, filters, paging, total.
```

A descrição completa para o LLM fica na allowlist
(`src/maximo_agents/mcp/allowlist.py`, `QUERY_WO_STATUS`).

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`
(= não informado). Textos exatos (até 100 caracteres) em [INSTALACAO.md](INSTALACAO.md).

| Variável | Obrigatória | Filtra |
|---|---|---|
| `date_from` | sim, exceto com `wonums` | `WOSTATUS.changedate >=` início do dia |
| `date_to` | sim, exceto com `wonums` | `WOSTATUS.changedate <` dia seguinte (inclusivo); máx 366 dias |
| `siteid` | não | `WOSTATUS.siteid` |
| `wonums` | não | `WOSTATUS.wonum` (máx 50); dispensa as datas |
| `status` | não | `WOSTATUS.status` (status para o qual a OS foi), valor gravado |
| `changeby` | não | `WOSTATUS.changeby` |
| `assetnum` | não | `WORKORDER.assetnum` da OS (subconsulta) |
| `location` | não | `WORKORDER.location` da OS (subconsulta) |
| `persongroup` | não | `WORKORDER.persongroup` da OS (subconsulta) |
| `worktype` | não | `WORKORDER.worktype` da OS (subconsulta) |
| `fields` | não | Padrão `wonum, siteid, status, changedate, changeby, memo`; também `orgid`, `wostatusid` |
| `page` | não | Página, a partir de 1 |
| `page_size` | não | 1 a 500 (padrão 100) |

Ordem: `wonum, siteid, changedate, wostatusid` (histórico de cada OS, mais antigo
primeiro). Sem `text`: a observação (`memo`) é curta e de uso irregular; entra se o
guia da Itambé pedir.

## Colunas

WOSTATUS não tem estrutura de objeto no `apischema` (MXAPIWODETAIL não traz o filho;
MXAPIWOSTATUS e MXWOSTATUS dão HTTP 500 `mosInfo`). O script lê a tabela direto com
`MboSet`. As colunas usadas são as padrão do Maximo (`wonum`, `siteid`, `orgid`,
`status`, `changedate`, `changeby`, `memo`, `wostatusid`); confirmar na 1ª chamada
(campo inexistente dá `internal_error`, com o nome no log).

## Garantias do script

- Somente leitura: nenhuma chamada de escrita. `MboSet` `DISCARDABLE`, `cleanup()`
  em `finally`.
- Valores só por bind (`SqlFormat`); colunas de listas fixas (`LIST_FILTERS`,
  `WO_FILTERS`, `FIELD_TYPES`).
- Escopo de OS sempre aplicado (`exists` em WORKORDER por `wonum` e `siteid`).
- Limites: 366 dias, 50 wonum, 20 valores por lista, 500 por página.
- Identidade obrigatória; permissão READ em WOTRACK checada no código; filtro de
  sites autorizados sempre aplicado (pelo `siteid` da própria mudança).
- **Site sempre explícito:** sem `siteid`, o script lê os sites autorizados do
  usuário (tabela SITE, mesma regra) e põe `siteid in (...)`. Sem site autorizado:
  `not_authorized`. Motivo: o índice por data `WOSTATUS_NDX1` é `SITEID, CHANGEDATE,
  WONUM` e o `exists ... or siteid in` da autorização não deixa o banco usá-lo.
  Homologação (2026-11-04), outubro/2026, 1510 mudanças: **196 s sem site, 5 s com**.
  Índices da Itambé: `NDX1` (SITEID, CHANGEDATE, WONUM), `NDX2` (SITEID, WONUM),
  `NDX3` (SITEID, STATUS).
- `count()` uma vez para o `total` (= número de mudanças, não de OS).

## Bloco comum

Trecho entre `# --- BEGIN COMMON` e `# --- END COMMON ---` copiado do
`QUERYWORKORDERS` sem mudança. `tests/unit/test_script_common.py` falha se divergir.

## Validar em homologação

1ª instalação em 2026-11-04 (cliente avulso pelo SDK MCP; o conector do claude.ai só
vê ferramentas registradas antes do início da sessão).

- [x] 13 parâmetros. 1ª vez veio `chengeby` (digitado errado), recriado como
      `changeby`. Description do script com 2 `u200b` no início (cosmético).
- [x] `wonums` sem datas → histórico completo em ordem (ex.: AGEXECFIL → APROG →
      AGINSP → CONCL), cerca de 3 s.
- [x] Outubro/2026 → 1510 mudanças (CONCL, EMAND, PREVCAN...; `memo` às vezes
      "Iniciado pelo Mobile").
- [x] `changeby`, `status`, `location` e `worktype` (pela OS) filtram certo.
- [x] Sem `date_to` → `required`; 367 dias → `range_too_large`; `unknown_field`.
- [x] Campos `memo`, `orgid`, `wostatusid` existem.
- [x] Site explícito (versão 2, reinstalada): outubro sem `siteid` 4 s (antes
      196 s); 366 dias → 50204 mudanças em 4 s; página 100 de 101 (500 itens) 5 s.
- [ ] Usuário sem READ em WOTRACK recebe `not_authorized`.
- [ ] Usuário **sem** acesso a um site não recebe mudanças desse site.
