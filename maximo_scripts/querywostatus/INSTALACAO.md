# Instalação do QUERYWOSTATUS no Maximo (passo a passo)

Ambiente: homologação Itambé (MAS 9.2, Maximo Manage). Mesmo roteiro do
`QUERYWORKORDERS` (detalhes e problemas comuns em `../queryworkorders/INSTALACAO.md`).
Regra do projeto: o conteúdo colado no Maximo é **exatamente** o do repositório.

## Atenção: caracteres invisíveis (U+200B)

- **Digitar à mão** o nome do script, os nomes das variáveis e o Title da MCP Tool.
- Código, schema e descrições: copiar do arquivo aberto no **editor de texto**.
- O passo 4 confere.

## 0. Antes de começar

- Usuário com acesso ao app **Automation Scripts** (em homologação: MAXADMIN).
- Abrir no editor: `QUERYWOSTATUS.py` e `response_schema.json` desta pasta.
- Anotar o commit (`git log -1 --oneline`).

## Atualizar instalação existente (2026-11-04: site explícito)

Se o `QUERYWOSTATUS` já está instalado: abrir o script, aba Main / Source Code,
apagar tudo e colar **todo** o `QUERYWOSTATUS.py` novo. **Save**. Variáveis, schema e
MCP Tool não mudam. Ao mesmo tempo, redigitar a **Description** (veio com `u200b`).

## 1. Criar o script (wizard)

Menu → **System Configuration → Platform Configuration → Automation Scripts** →
**More Actions → Create → Script** (sem launch point).

### Passo 1 do wizard – dados do script

| Campo | Valor |
|---|---|
| Script | `QUERYWOSTATUS` (digitar) |
| Description | `Read-only work order status history: date range (YYYY-MM-DD) or wonums, filters, paging, total.` |
| Script Language | `python` (se não houver, `jython`) |
| Log Level | `DEBUG` (só durante a validação; voltar para `ERROR` no passo 7) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

### Passo 2 do wizard – variáveis

Criar **13 linhas**. Em todas: Variable Type `IN`, Binding Type `LITERAL`, Literal
Data Type `ALN`, Binding Value `*`. Nome **digitado em minúsculas**.

| Variable | Description |
|---|---|
| `date_from` | Start of status change date range, YYYY-MM-DD, inclusive. Required unless wonums is given. |
| `date_to` | End date, YYYY-MM-DD, inclusive. Max 366 days after date_from. Required unless wonums is given. |
| `siteid` | Site IDs, comma-separated (max 20). |
| `wonums` | Work order numbers, comma-separated (max 50). Dates optional when given. |
| `status` | Status the work order changed to, comma-separated (max 20). |
| `changeby` | User IDs who changed the status, comma-separated (max 20). |
| `assetnum` | Asset numbers of the work order, comma-separated (max 20). |
| `location` | Location codes of the work order, comma-separated (max 20). |
| `persongroup` | Crew/person group codes of the work order, comma-separated (max 20). |
| `worktype` | Work types of the work order, comma-separated (max 20). |
| `fields` | Fields to return, comma-separated. wonum and siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100). |

**Não criar `authapp` nem `authsigoption`**: toda variável vira parâmetro da
ferramenta. A permissão (WOTRACK/READ) é checada no código.

### Passo 3 do wizard – código

Colar **todo** o `QUERYWOSTATUS.py` em Source Code. **Create**. Se der erro de
compilação: copiar a mensagem exata e parar (não corrigir no Maximo).

## 2. Response Schema

Aba Main, campo **Response Schema**: colar `response_schema.json`. **Save**.

## 3. Publicar como ferramenta MCP

**More Actions → Add/Modify MCP Tool**.

| Campo | Valor |
|---|---|
| Title | `Query work order status history` (digitar) |
| Processing notes | `Pass date_from and date_to, except when looking up specific wonums (full history, dates optional). Use "*" for unused parameters. "total" counts status changes, not work orders. If "has_more" is true, request the next page or narrow the filters.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

**OK** e **Save**.

## 4. Conferir no Manage

`https://<host-do-manage>/maximo/api/oas?aitools=1`, com Ctrl+F:

- [ ] `script_querywostatus` aparece.
- [ ] **`u200b` não aparece** no trecho de `/script_querywostatus`.
- [ ] `authapp` e `authsigoption` não aparecem.
- [ ] 13 parâmetros no `requestBody`.

## 5. Conferir no MCP Server

O pod lê a lista a cada 10 min. **Não** reiniciar o pod. Depois de 10 min, me avisar:
eu chamo a ferramenta pelo conector.

## 6. Testes (feitos por mim via MCP; para referência)

1. `{"wonums": "<OS concluída conhecida>"}` → histórico completo, em ordem.
2. `{"date_from": "2026-10-01", "date_to": "2026-10-31", "page_size": "5"}` → `total`
   e 5 itens.
3. Mesmo período com `location` ou `assetnum` conhecido → só mudanças dessas OS.
4. `{"date_from": "2026-10-01"}` → `required` em `date_to`.
5. `fields` = `memo,orgid,wostatusid` → sem `internal_error`.

Log (DEBUG): linha `QUERYWOSTATUS implicit vars: [...]; param sources: {...}`.

## 7. Fechar

- **Log Level** do script para `ERROR`. Save.
- Me avisar o commit instalado.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| Erro de compilação no Create | Copiar a mensagem; não editar no Maximo. |
| `u200b` no OAS | Apagar a variável (ou o script) e recriar digitando o nome. |
| `internal_error` | Log do Manage: `QUERYWOSTATUS failed: ...` (ex.: coluna inexistente). Me enviar. |
| `not_authorized` | Usuário da `apikey` sem READ em WOTRACK. |
| `total` = 0 com certeza de haver mudanças | Me enviar a linha de SQL do log (autoscript em DEBUG). |
| Lento em 366 dias | Me avisar o tempo; limitar o período ou rever a subconsulta. |
