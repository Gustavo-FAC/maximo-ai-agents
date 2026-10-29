# QUERYASSETS

Consulta genérica de ativos, somente leitura. Publicada no MCP Server como automation
script. Junto com o `QUERYWORKORDERS`, cobre "histórico do ativo" (cadastro e situação
aqui; OS do ativo lá, com filtro `assetnum`).

| Item | Valor |
|---|---|
| Script | `QUERYASSETS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objeto | `ASSET` |
| Arquivos | `QUERYASSETS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_queryassets.py` (lógica pura, CPython) e `tests/unit/test_script_common.py` (bloco comum) |

## Descrição da ferramenta (colar no campo Description)

```text
Read-only asset search: filters, hierarchy, description words, paging, total.
```

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`
(= não informado). Descrições com até 100 caracteres; textos exatos em
[INSTALACAO.md](INSTALACAO.md).

| Variável | Descrição |
|---|---|
| `siteid` | Site IDs, comma-separated (max 20). |
| `assetnums` | Asset numbers, comma-separated (max 50). |
| `ancestor` | Asset numbers (max 20); returns assets anywhere below them in the hierarchy. |
| `status` | Asset status values, comma-separated (max 20), e.g. OPERATING. |
| `location` | Location codes, comma-separated (max 20). |
| `parent` | Parent asset numbers, comma-separated (max 20); direct children only. |
| `assettype` | Asset types, comma-separated (max 20). |
| `priority` | Priority integers, comma-separated (max 20). |
| `failurecode` | Failure class codes, comma-separated (max 20). |
| `text` | Words that must all appear in the description (max 5 words, 100 chars). |
| `fields` | Fields to return, comma-separated. assetnum and siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100). |

Nenhum filtro obrigatório: ativo é cadastro, a resposta é limitada por `page_size` e
`total` é exato. Campos aceitos em `fields`: ver `FIELD_TYPES` no script.

Só atributos padrão do ASSET. Campos próprios do cliente (na Itambé, a matriz de
criticidade `cci_*`) quebram em outro cliente; entram depois, como extensão, quando
o guia da Itambé explicar o significado de cada um.

## Garantias do script

- Somente leitura: nenhuma chamada de `setValue`, `save` ou `changeStatus`.
  `MboSet` com flag `DISCARDABLE` e `cleanup()` em `finally`.
- Valores dos filtros só entram por bind (`SqlFormat.setObject`). Colunas vêm de
  listas fixas (`LIST_FILTERS`, `FIELD_TYPES`).
- `text`: cada palavra vira `upper(description) like :n` com `%palavra%` no bind.
  `%` e `_` recusados (seriam curinga e o escape muda entre bancos).
- Limites validados no script: 50 assetnums, 20 valores por lista, 5 palavras,
  500 por página.
- Identidade obrigatória; sem ela, erro `no_user`.
- Permissão READ no app ASSET checada no código (APPLICATIONAUTH); sem ela,
  `not_authorized`. Sem variáveis `authapp`/`authsigoption`.
- Filtro de sites autorizados ao usuário sempre aplicado.
- `count()` chamado uma vez para o `total`.

## Bloco comum

O trecho entre `# --- BEGIN COMMON` e `# --- END COMMON ---` é igual em todos os
scripts (decisão 2026-10-29: copiar, sem script biblioteca). Mudou em um, muda em
todos; `tests/unit/test_script_common.py` falha se divergir.

## Validar em homologação (antes de usar com gerente)

Validado em 2026-10-29 (Itambé, chave MAXADMIN): marcados com [x].

- [x] Ferramenta aparece no MCP com 13 parâmetros, sem caracteres invisíveis.
- [x] Sem parâmetros: `total` = número de ativos dos sites do usuário (14709).
- [x] `assetnums` com 2 ativos conhecidos → `total` 2.
- [x] `text` com palavras de descrição conhecidas acha o ativo; acento precisa
      bater ("elétrico" acha, "eletrico" não); `%` e palavra de 1 letra recusados.
- [x] `ancestor` devolve todos os níveis (ACI0008 → ACI0057 → PEL0007).
      ASSETANCESTOR tem linha do ativo com ele mesmo: na 1ª instalação o próprio
      ativo vinha junto (CCM2.1: 22 = 21 filhos + ele). Corrigido no SQL
      (`aa.assetnum <> aa.ancestor`) e conferido após reinstalar: CCM2.1 → 21,
      ACI0008 → 2, os dois juntos → 23, ativo sem filhos → 0.
- [x] `fields` com `children`, `installdate`, `statusdate`, `purchaseprice`
      devolve booleano, data ISO e número.
- [x] Paginação (página 2), `unknown_field`, `invalid_integer` ok.
- [ ] Usuário sem READ no app ASSET recebe `not_authorized`.
- [ ] Usuário **sem** acesso a um site não recebe ativos desse site.
