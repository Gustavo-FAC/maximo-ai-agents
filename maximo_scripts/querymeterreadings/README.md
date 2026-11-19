# QUERYMETERREADINGS

Consulta genérica de leituras de medidores e de Monitoramento de Condições, somente
leitura. Pedido do usuário em 2026-11-19 (fora das 17 perguntas do guia da Itambé).
**Falta confirmar se a Itambé registra leituras no Maximo**: até lá a ferramenta fica
fora dos agentes (`DORMANT_TOOLS`), liberada só no Claude Code.

| Item | Valor |
|---|---|
| Script | `QUERYMETERREADINGS` (sem launch point) |
| Linguagem | Jython 2.7 (`python`) |
| Objetos | `MEASUREMENT` (padrão) ou `METERREADING` (`reading_type=continuous`); `METER` e `MEASUREPOINT` para a página |
| Permissão | READ no app `ASSET` (checada no código) |
| Arquivos | `QUERYMETERREADINGS.py`, `response_schema.json`, `INSTALACAO.md` |
| Testes | `tests/unit/test_querymeterreadings.py` e `tests/unit/test_script_common.py` (bloco comum) |

## Onde o Maximo guarda as leituras

| Tabela | Conteúdo |
|---|---|
| `MEASUREMENT` | Leituras de medidores de **indicador** (gauge: temperatura, vibração) e de **característica** (valor de domínio, vai em `observation`), de ativo ou location, inclusive dos **pontos de Monitoramento de Condições** (`pointnum`). |
| `METERREADING` | Leituras de medidores **contínuos** de ativo (horímetro, contador), com `delta` desde a anterior. |
| `METER` | Cadastro do medidor: tipo, **unidade** (`measureunitid`), domínio. |
| `MEASUREPOINT` | Ponto de medição: limites de alerta (`upperwarning`/`lowerwarning`) e de ação (`upperaction`/`loweraction`). |

Fora: leituras de medidor contínuo de **location** (`LOCMETERREADING`) e o cadastro
dos medidores no ativo (`ASSETMETER`: última leitura, média). Maximo Monitor/Health
(IoT) guarda dado fora do Manage: não coberto.

## Descrição da ferramenta (colar no campo Description)

```text
Read-only meter readings: measurement (gauge, condition monitoring) or continuous, by date.
```

## Variáveis (aba Variables)

Todas: tipo **IN**, binding **Literal**, `literaldatatype` **ALN**, valor padrão `*`
(= não informado). Descrições com até 100 caracteres.

| Variável | Descrição |
|---|---|
| `date_from` | Start of reading date range, YYYY-MM-DD, inclusive. Required. |
| `date_to` | End date, YYYY-MM-DD, inclusive. Max 366 days after date_from. Required. |
| `reading_type` | measurement (default: gauge, characteristic, condition monitoring) or continuous. |
| `siteid` | Site IDs, comma-separated (max 20). |
| `assetnum` | Asset numbers, comma-separated (max 50). |
| `location` | Location codes, comma-separated (max 20). Measurement only. |
| `metername` | Meter names, comma-separated (max 20). |
| `pointnum` | Condition monitoring point numbers, comma-separated (max 20). Measurement only. |
| `inspector` | Person IDs who took the reading, comma-separated (max 20). |
| `fields` | Fields to return, comma-separated. assetnum, siteid, metername, readingdate always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100). |

Campos aceitos em `fields`: `FIELD_TYPES` no script. Os nomes de saída são os
mesmos nos dois tipos (`readingdate` = `measuredate` ou `readingdate`; `reading` =
`measurementvalue` ou `reading`; `readingid` = `measurementid` ou `meterreadingid`).

## Garantias do script

- Somente leitura; `MboSet` com `DISCARDABLE` e `cleanup()` em `finally`.
- Valores só por bind; colunas de listas fixas (`READING_TYPES`, `LIST_FILTERS`,
  `FIELD_TYPES`).
- Intervalo de datas **sempre** obrigatório (movimento), até 366 dias.
- Permissão READ no app `ASSET` checada no código; sites autorizados sempre
  aplicados; sem `siteid`, os sites autorizados entram explícitos (`siteid in (...)`,
  lição do `QUERYWORKORDERS`).
- Filtro de campo que o tipo não tem (`location`, `pointnum` com `continuous`):
  erro `not_supported`.
- Campos conferidos no dicionário de dados (`getMaximoDD`): campo pedido que o tipo
  ou este Maximo não tem sai dos itens e vai em `fields_unavailable` (sem
  BMXAA4176E, lição do `QUERYSRS`).
- `meters`: medidores da página (`metername in (...)`, até `page_size`). `points`
  (só `measurement`): pontos da página por `pointnum` e site, com autorização por
  site; pares fora da página descartados.

## Bloco comum

Trecho entre `# --- BEGIN COMMON` e `# --- END COMMON ---` igual ao do `QUERYASSETS`.
`tests/unit/test_script_common.py` falha se divergir.

## Validar em homologação

- [ ] Itambé usa medidores/Monitoramento de Condições? (apps Medidores e
      Monitoramento de Condições; leituras recentes em quais ativos?)
- [ ] Índices de `MEASUREMENT` e `METERREADING` (Database Configuration).
- [ ] Ferramenta aparece no MCP com 12 parâmetros.
- [ ] Um ano de `measurement` e de `continuous`: `total` coerente com o app.
- [ ] `meters` traz a unidade; `points` traz os limites.
- [ ] `fields_unavailable` vazio no padrão (atributos existem na Itambé).
- [ ] `location` com `continuous` dá `not_supported`; sem datas dá `required`.
- [ ] Depois de confirmado o uso: tirar de `DORMANT_TOOLS` e pôr na receita.
