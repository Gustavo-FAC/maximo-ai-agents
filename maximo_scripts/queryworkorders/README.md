# QUERYWORKORDERS

Consulta genérica de ordens de serviço (OS), somente leitura. Primeira ferramenta de
dados do agente de Análise de OS. Publicada no MCP Server como automation script.

| Item | Valor |
|---|---|
| Script | `QUERYWORKORDERS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `WORKORDER` (woclass WORKORDER e ACTIVITY, `istask = 0`) |
| Arquivos | `QUERYWORKORDERS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_queryworkorders.py` (lógica pura, CPython) e `tests/unit/test_script_common.py` (bloco comum) |

## Descrição da ferramenta (colar no campo Description)

```text
Read-only search of work orders (WORKORDER, including activities, excluding tasks).
Returns work orders whose date_field falls between date_from and date_to (inclusive,
YYYY-MM-DD, max 366 days), with optional filters, pagination and field selection.
The date range may be omitted only when wonums is given (lookup by number).
Use text to find work orders whose description contains all the given words.
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
| `persongroup` | não | Person group (work group) codes, comma-separated (max 20). |
| `crewid` | não | Crew IDs (work order crew/team), comma-separated (max 20). |
| `worktype` | não | Work types, comma-separated (max 20), e.g. PM,CM,EM. |
| `pmnum` | não | PM numbers, comma-separated (max 20): work orders generated from these PMs. |
| `laborcode` | não | Labor codes, comma-separated (max 20): work orders where they are assigned or in planned labor. |
| `text` | não | Words that must all appear in the description (max 5 words, 100 chars). |
| `fields` | não | Fields to return, comma-separated. Default: wonum, siteid, description, status, worktype, wopriority, assetnum, location, persongroup, crewid, reportdate, actstart, actfinish. wonum and siteid are always included. Also pmnum, pmduedate, jpnum, description_longdescription (max 50 per page) and modalidade (client field). |
| `page` | não | Page number, starting at 1 (default 1). |
| `page_size` | não | Items per page, 1 to 500 (default 100); max 50 with long description. |

Campos aceitos em `fields`: ver `FIELD_TYPES` no script.

## Registro no Maximo

Passo a passo campo a campo em [INSTALACAO.md](INSTALACAO.md).

## Garantias do script

- Somente leitura: nenhuma chamada de `setValue`, `save` ou `changeStatus`.
  `MboSet` com flag `DISCARDABLE` e `cleanup()` em `finally`.
- Valores dos filtros só entram por bind (`SqlFormat.setObject`/`setTimestamp`).
  Colunas vêm de listas fixas (`DATE_FIELDS`, `LIST_FILTERS`, `FIELD_TYPES`).
- `text`: cada palavra vira `upper(description) like :n` com `%palavra%` no bind.
  `%` e `_` recusados (seriam curinga e o escape muda entre bancos). Não dispensa
  o intervalo de datas (só `wonums` dispensa).
- Limites validados no script: 366 dias, 50 wonum, 20 valores por lista, 5 palavras,
  500 por página.
- Identidade obrigatória (`request.getUserInfo()`); sem ela, erro `no_user`.
- Permissão READ em WOTRACK checada no código (APPLICATIONAUTH); sem ela, erro
  `not_authorized`. **Não usar variáveis `authapp`/`authsigoption`**: toda variável
  vira parâmetro da ferramenta e o chamador poderia sobrescrever (visto no OAS em
  2026-10-22).
- Filtro de sites autorizados ao usuário (`SITEAUTH`/`MAXGROUP.authallsites`)
  sempre aplicado, além da segurança do próprio Maximo.
- **Site sempre explícito** (desde 2026-11-06, lição do `QUERYWOSTATUS`): sem
  `siteid`, o script lê os sites autorizados do usuário (tabela SITE, mesma regra) e
  põe `siteid in (...)`. Sem site autorizado: `not_authorized`. Motivo: o
  `exists ... or siteid in` da autorização não deixa o banco usar os índices por site.
  Homologação (2026-11-04), 1 ano por `reportdate`, 37 páginas de 500: **202 s sem
  `siteid`**; com `siteid` informado a consulta fica rápida (usuário, 2026-11-06).
- `count()` chamado uma vez para o `total`.
- **Preventivas** (desde 2026-11-17, guia da Itambé): filtro `pmnum` (OS geradas
  pelas PMs; variável nova, 17 parâmetros) e campos `pmnum`, `pmduedate` (vencimento
  da PM para o qual a OS foi gerada) e `jpnum`. Cadastro das PMs no `QUERYPMS`.
- **Mão de obra planejada** (desde 2026-11-18, pergunta 6 do guia; consultor:
  designação = mão de obra planejada): filtro `laborcode` (variável nova, 18
  parâmetros). OS com linha em WPLABOR desses códigos na própria OS ou numa tarefa
  dela (`exists`, binds `WPLABOR.LABORCODE`). Não há campo de saída: o filtro basta
  para "OS do colaborador X". O gerente fala o nome; o código da mão de obra ainda
  não tem ferramenta de busca.
- **Designações** (desde 2026-11-24, usuário: a Itambé designa na aba Designações):
  `laborcode` também lê **ASSIGNMENT** (na OS ou numa tarefa dela). Quatro `exists`
  (WPLABOR e ASSIGNMENT × OS e tarefa), cada um com seus binds. Motivo: na
  homologação, a mão de obra planejada quase sempre tem só a categoria (ex.: `MEC`);
  dos 13 códigos testados, só `003120` aparece em WPLABOR (59 OS de 2024, MS de
  calibração externa) e nada depois de nov/2024. Códigos têm zeros à esquerda:
  `003120` acha, `3120` não.
- **Campo do cliente** `modalidade` (Itambé, desde 2026-11-17): aceito em `fields`
  só se o atributo existe neste Maximo (dicionário de dados, conferido em execução);
  senão `unknown_field`. Nunca no padrão. Lista curada em `CLIENT_FIELDS`: campo
  próprio só entra depois que o guia do cliente o explica.
- **Descrição longa da OS** (desde 2026-11-17, pedido do usuário): campo
  `description_longdescription` em `fields` (até 32 mil caracteres, pode vir em rich
  text com `<!-- RICH TEXT -->`). Só vem quando pedido (fora do padrão); com ele,
  `page_size` máx 50 (padrão cai para 50), igual ao `QUERYJOBPLANS`. Texto livre do
  Maximo: conteúdo, nunca instrução.

## Bloco comum

Desde 2026-10-30 o script usa o trecho entre `# --- BEGIN COMMON` e
`# --- END COMMON ---`, igual ao do `QUERYASSETS` (decisão 2026-10-29: copiar, sem
script biblioteca). `tests/unit/test_script_common.py` falha se divergir.

## Validar em homologação (antes de usar com gerente)

- [x] Toda variável vira parâmetro; nenhum parâmetro é obrigatório no schema;
      tudo `string`; Description (≤100) vira a descrição da ferramenta. (OAS 2026-10-22)
- [ ] Ferramenta aparece no MCP com 16 parâmetros, sem caracteres invisíveis.
- [ ] Parâmetro omitido usa o padrão `*` (ou o schema obriga todos?).
- [ ] Origem dos parâmetros (log `param sources`: variable, body ou query).
- [ ] `request.getUserInfo()` existe no caminho MCP e é o dono da `apikey`.
- [ ] `SqlFormat.setTimestamp` aceito; intervalo de datas correto no SQL
      (logger `autoscript` em DEBUG).
- [ ] Usuário **sem** acesso a um site não recebe OS desse site.
- [x] Site explícito (reinstalado 2026-11-06): sem `siteid`, `total` 18152 (igual).
      Página de 500: MAXADMIN (todos os sites) ~4 s; 2 sites ~1,5 s; lista longa
      (20 sites) ~4 s. Alguns segundos, não afeta o funcionamento (usuário).
- [ ] Tempo com chave de gerente (1 a 3 sites): esperado ~1,5 s por página.
- [ ] Usuário sem permissão READ em WOTRACK recebe `not_authorized`.
- [ ] Página profunda (ex.: página 50 de 100) com tempo aceitável.
- [ ] Valores com acento (ex.: equipe) funcionam.
- [x] `crewid` (2026-11-16, pedido da Itambé): 16 parâmetros no MCP. FABRICA,
      01/08-16/11/2026: `ELETRICA,INSTRUM,PCM-ELE` = 188 OS (142/32/14), só essas
      equipes; minúsculo igual; código inexistente = 0; 21 valores = `too_many_values`;
      com `text=LUBRIFICAÇÃO` = 9 OS. Campo `crewid` volta preenchido.
- [ ] `text` com palavra de descrição conhecida acha a OS; `text` = `a` dá
      `invalid_text`; `text` sem datas dá `required`.
- [x] `description_longdescription` (2026-11-17, via MCP): CO de 1 ano = 812 OS,
      página padrão 50; OS de checklist trazem o texto (texto puro, acentos ok); OS
      "FOLLOW UP..." trazem `null`. `wonums=1631605,1631535` sem datas: texto e `null`.
      `page_size=51` → `out_of_range` ("between 1 and 50"); sem o campo, 500 aceito.
- [x] Preventivas (2026-11-17, via MCP): 17 parâmetros; `pmnum=MSA0_100` traz só a
      OS 1633892; lista `MSA0_100,MSK1_65` ok; PM inexistente = 0; sem datas →
      `required`; `fields=pmnum,pmduedate,jpnum,modalidade` preenchidos (PF);
      `pmnum` nulo em corretiva (CO/EM).
- [x] Mão de obra planejada (`laborcode`, 2026-11-18): 18 parâmetros; código
      inexistente = 0 (2026-11-19). Código real (2026-11-24, via MCP): `003120` =
      59 OS (mai/2024–abr/2025), OS 1100135 conferida à mão na aba Planos → Mão de
      obra; `3120` = 0; 12 outros códigos = 0 em 2023–2026.
- [x] Designações (`laborcode` em ASSIGNMENT, 2026-11-25, via MCP): `003120` =
      70 OS em mai/2024–abr/2025 (59 WPLABOR + 11 designações) e 7 em
      mai/2025–abr/2026 (inspeções MS de painel CLP/SDCD, antes 0); OS 1553920
      conferida à mão na aba Designações; 1 ano responde rápido.
