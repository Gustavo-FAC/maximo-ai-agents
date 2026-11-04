# Instalação do QUERYWOMATERIALS no Maximo (passo a passo)

Ambiente: homologação Itambé (MAS 9.2, Maximo Manage). Mesmo roteiro do
`QUERYWORKORDERS` (detalhes e problemas comuns em `../queryworkorders/INSTALACAO.md`).
Regra do projeto: o conteúdo colado no Maximo é **exatamente** o do repositório.

## Atenção: caracteres invisíveis (U+200B)

- **Digitar à mão** o nome do script, os nomes das variáveis, a Description e o Title da
  MCP Tool (o MCP usa a Description do script como descrição da ferramenta).
- Código, schema e descrições das variáveis: copiar do arquivo aberto no **editor de texto**.
- O passo 4 confere.

## 0. Antes de começar

- Usuário com acesso ao app **Automation Scripts** (em homologação: MAXADMIN).
- Abrir no editor: `QUERYWOMATERIALS.py` e `response_schema.json` desta pasta.
- Anotar o commit (`git log -1 --oneline`).

## 1. Criar o script (wizard)

Menu → **System Configuration → Platform Configuration → Automation Scripts** →
**More Actions → Create → Script** (sem launch point).

### Passo 1 do wizard – dados do script

| Campo | Valor |
|---|---|
| Script | `QUERYWOMATERIALS` (digitar) |
| Description | `Read-only planned materials of work orders: date range (YYYY-MM-DD) or wonums, filters, paging, total.` (digitar) |
| Script Language | `python` (se não houver, `jython`) |
| Log Level | `DEBUG` (só durante a validação; voltar para `ERROR` no passo 7) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

### Passo 2 do wizard – variáveis

Criar **16 linhas**. Em todas: Variable Type `IN`, Binding Type `LITERAL`, Literal
Data Type `ALN`, Binding Value `*`. Nome **digitado em minúsculas**.

| Variable | Description |
|---|---|
| `date_from` | Start of work order date range, YYYY-MM-DD, inclusive. Required unless wonums is given. |
| `date_to` | End date, YYYY-MM-DD, inclusive. Max 366 days after date_from. Required unless wonums is given. |
| `date_field` | Work order date for the range: reportdate (default), schedstart, targstartdate, actstart... |
| `siteid` | Site IDs, comma-separated (max 20). |
| `wonums` | Work order numbers, comma-separated (max 50). Includes their tasks. Dates optional. |
| `status` | Status of the work order, comma-separated (max 20). |
| `assetnum` | Asset numbers of the work order, comma-separated (max 20). |
| `location` | Location codes of the work order, comma-separated (max 20). |
| `persongroup` | Crew/person group codes of the work order, comma-separated (max 20). |
| `worktype` | Work types of the work order, comma-separated (max 20). |
| `itemnums` | Item numbers, comma-separated (max 50). |
| `storeloc` | Storerooms of the material lines, comma-separated (max 20). |
| `include_balance` | Y to add the storeroom balance of each line (page_size max 50). Default N. |
| `fields` | Fields to return, comma-separated. wonum and siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100; max 50 with include_balance). |

**Não criar `authapp` nem `authsigoption`**: toda variável vira parâmetro da
ferramenta. As permissões (WOTRACK/READ; INVENTOR/READ para saldo) são checadas no código.

### Passo 3 do wizard – código

Colar **todo** o `QUERYWOMATERIALS.py` em Source Code. **Create**. Se der erro de
compilação: copiar a mensagem exata e parar (não corrigir no Maximo).

## 2. Response Schema

Aba Main, campo **Response Schema**: colar `response_schema.json`. **Save**.

## 3. Publicar como ferramenta MCP

**More Actions → Add/Modify MCP Tool**.

| Campo | Valor |
|---|---|
| Title | `Query work order planned materials` (digitar) |
| Processing notes | `Pass date_from and date_to, except when looking up specific wonums (dates optional). Use "*" for unused parameters. "total" counts material lines. If "has_more" is true, request the next page or narrow the filters.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

**OK** e **Save**.

## 4. Conferir no Manage

`https://<host-do-manage>/maximo/api/oas?aitools=1`, com Ctrl+F:

- [ ] `script_querywomaterials` aparece.
- [ ] **`u200b` não aparece** no trecho de `/script_querywomaterials`.
- [ ] `authapp` e `authsigoption` não aparecem.
- [ ] 16 parâmetros no `requestBody`.

## 5. Conferir no MCP Server

O pod lê a lista a cada 10 min. **Não** reiniciar o pod. Depois de 10 min, me avisar:
eu chamo a ferramenta pelo conector.

## 6. Testes (feitos por mim via MCP; para referência)

1. `{"date_from": "2026-10-01", "date_to": "2026-10-31", "page_size": "5"}` → `total` e 5
   linhas; anotar o tempo.
2. `{"wonums": "<OS com material planejado>"}` → linhas, inclusive de tarefas (`taskid`).
3. Mesmo `wonums` com `include_balance=Y` → `balance` em cada linha.
4. `fields` com todos os opcionais → sem `internal_error`.
5. `{"date_from": "2026-10-01"}` → `required` em `date_to`.

Log (DEBUG): linha `QUERYWOMATERIALS implicit vars: [...]; param sources: {...}`.

## 7. Fechar

- **Log Level** do script para `ERROR`. Save.
- Me avisar o commit instalado.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| Erro de compilação no Create | Copiar a mensagem; não editar no Maximo. |
| `u200b` no OAS | Apagar a variável (ou o script) e recriar digitando o nome. |
| `internal_error` | Log do Manage: `QUERYWOMATERIALS failed: ...` (ex.: coluna inexistente, NullPointerException ao ler WPMATERIAL sem a OS). Me enviar. |
| `not_authorized` | Usuário da `apikey` sem READ em WOTRACK (ou INVENTOR, com saldo). |
| `total` = 0 com OS que tem material | Me enviar a linha de SQL do log (pode ser `wogroup` vazio). |
| Lento | Me avisar o tempo; conferir índices de WPMATERIAL em Database Configuration. |
