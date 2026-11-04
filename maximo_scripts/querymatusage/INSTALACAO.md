# Instalação do QUERYMATUSAGE no Maximo (passo a passo)

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
- Abrir no editor: `QUERYMATUSAGE.py` e `response_schema.json` desta pasta.
- Anotar o commit (`git log -1 --oneline`).

## 1. Criar o script (wizard)

Menu → **System Configuration → Platform Configuration → Automation Scripts** →
**More Actions → Create → Script** (sem launch point).

### Passo 1 do wizard – dados do script

| Campo | Valor |
|---|---|
| Script | `QUERYMATUSAGE` (digitar) |
| Description | `Read-only material usage (issues and returns): date range (YYYY-MM-DD) or wonums, filters, paging, total.` (digitar) |
| Script Language | `python` (se não houver, `jython`) |
| Log Level | `DEBUG` (só durante a validação; voltar para `ERROR` no passo 7) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

### Passo 2 do wizard – variáveis

Criar **15 linhas**. Em todas: Variable Type `IN`, Binding Type `LITERAL`, Literal
Data Type `ALN`, Binding Value `*`. Nome **digitado em minúsculas**.

| Variable | Description |
|---|---|
| `date_from` | Start of transaction date range, YYYY-MM-DD, inclusive. Required unless wonums is given. |
| `date_to` | End date, YYYY-MM-DD, inclusive. Max 366 days after date_from. Required unless wonums is given. |
| `date_field` | Transaction date for the range: actualdate (default) or transdate. |
| `siteid` | Site IDs (storeroom site), comma-separated (max 20). |
| `wonums` | Work order numbers, comma-separated (max 50). Includes their tasks. Dates optional. |
| `itemnums` | Item numbers, comma-separated (max 50). |
| `storeloc` | Storerooms, comma-separated (max 20). |
| `assetnum` | Asset numbers charged, comma-separated (max 20). |
| `location` | Location codes charged, comma-separated (max 20). |
| `issuetype` | issue or return. Default: both. |
| `worktype` | Work types of the work order, comma-separated (max 20). |
| `persongroup` | Crew/person group codes of the work order, comma-separated (max 20). |
| `fields` | Fields to return, comma-separated. refwo, siteid and matusetransid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100). |

**Não criar `authapp` nem `authsigoption`**: toda variável vira parâmetro da
ferramenta. A permissão (WOTRACK/READ) é checada no código.

### Passo 3 do wizard – código

Colar **todo** o `QUERYMATUSAGE.py` em Source Code. **Create**. Se der erro de
compilação: copiar a mensagem exata e parar (não corrigir no Maximo).

## 2. Response Schema

Aba Main, campo **Response Schema**: colar `response_schema.json`. **Save**.

## 3. Publicar como ferramenta MCP

**More Actions → Add/Modify MCP Tool**.

| Campo | Valor |
|---|---|
| Title | `Query material usage` (digitar) |
| Processing notes | `Pass date_from and date_to, except when looking up specific wonums (dates optional). Use "*" for unused parameters. "total" counts transactions. quantity is negative for issues. If "has_more" is true, request the next page.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

**OK** e **Save**.

## 4. Conferir no Manage

`https://<host-do-manage>/maximo/api/oas?aitools=1`, com Ctrl+F:

- [ ] `script_querymatusage` aparece.
- [ ] **`u200b` não aparece** no trecho de `/script_querymatusage`.
- [ ] `authapp` e `authsigoption` não aparecem.
- [ ] 15 parâmetros no `requestBody`.

## 5. Conferir no MCP Server

O pod lê a lista a cada 10 min. **Não** reiniciar o pod. Depois de 10 min, me avisar:
eu chamo a ferramenta pelo conector.

## 6. Testes (feitos por mim via MCP; para referência)

1. `{"date_from": "2026-10-01", "date_to": "2026-10-31", "page_size": "5"}` → `total` e 5
   linhas; anotar o tempo.
2. `{"wonums": "<OS com baixa de material>"}` → linhas, inclusive de tarefas.
3. `issuetype=return` → só devoluções, `quantity` positivo.
4. `fields` com todos os opcionais → sem `internal_error`.
5. `{"date_from": "2026-10-01"}` → `required` em `date_to`.

Log (DEBUG): linha `QUERYMATUSAGE implicit vars: [...]; param sources: {...}`.

## 7. Fechar

- **Log Level** do script para `ERROR`. Save.
- Me avisar o commit instalado.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| Erro de compilação no Create | Copiar a mensagem; não editar no Maximo. |
| `u200b` no OAS | Apagar a variável (ou o script) e recriar digitando o nome. |
| `internal_error` | Log do Manage: `QUERYMATUSAGE failed: ...`. Me enviar. |
| `not_authorized` | Usuário da `apikey` sem READ em WOTRACK. |
| Lento em 366 dias | Me avisar o tempo; conferir índices de MATUSETRANS em Database Configuration. |
