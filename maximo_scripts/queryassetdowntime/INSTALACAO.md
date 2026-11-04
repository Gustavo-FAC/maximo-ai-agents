# Instalação do QUERYASSETDOWNTIME no Maximo (passo a passo)

Ambiente: homologação Itambé (MAS 9.2, Maximo Manage). Mesmo roteiro do
`QUERYWOSTATUS` (detalhes e problemas comuns em `../queryworkorders/INSTALACAO.md`).
Regra do projeto: o conteúdo colado no Maximo é **exatamente** o do repositório.

## Atenção: caracteres invisíveis (U+200B)

- **Digitar à mão** o nome do script, a Description, os nomes das variáveis e o Title
  da MCP Tool. Ctrl+A + Delete antes de digitar limpa o início do campo.
- Código e schema: copiar do arquivo aberto no **editor de texto**.
- O passo 4 confere.

## 0. Antes de começar

- Usuário com acesso ao app **Automation Scripts** (em homologação: MAXADMIN).
- Abrir no editor: `QUERYASSETDOWNTIME.py` e `response_schema.json` desta pasta.
- Anotar o commit (`git log -1 --oneline`).
- **Índices da ASSETSTATUS:** Database Configuration → objeto `ASSETSTATUS` → aba
  Indexes → View Details em cada um. Me mandar as colunas (para registrar e explicar
  o tempo das consultas).

## 1. Criar o script (wizard)

Menu → **System Configuration → Platform Configuration → Automation Scripts** →
**More Actions → Create → Script** (sem launch point).

### Passo 1 do wizard – dados do script

| Campo | Valor |
|---|---|
| Script | `QUERYASSETDOWNTIME` (digitar) |
| Description | `Read-only asset downtime history: date range (YYYY-MM-DD) or assetnums, filters, paging, total.` (digitar) |
| Script Language | `python` (se não houver, `jython`) |
| Log Level | `DEBUG` (só durante a validação; voltar para `ERROR` no passo 7) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

### Passo 2 do wizard – variáveis

Criar **12 linhas**. Em todas: Variable Type `IN`, Binding Type `LITERAL`, Literal
Data Type `ALN`, Binding Value `*`. Nome **digitado em minúsculas**.

| Variable | Description |
|---|---|
| `date_from` | Start of change date range, YYYY-MM-DD, inclusive. Required unless assetnums or wonums is given. |
| `date_to` | End date, YYYY-MM-DD, inclusive. Max 366 days after date_from. Required unless assetnums/wonums. |
| `siteid` | Site IDs, comma-separated (max 20). |
| `assetnums` | Asset numbers, comma-separated (max 50). Dates optional when given. |
| `location` | Location codes recorded on the change, comma-separated (max 20). |
| `wonums` | Work order numbers recorded on the change, comma-separated (max 50). Dates optional when given. |
| `code` | Downtime codes, comma-separated (max 20). |
| `event` | down (asset went down) or up (asset came back up). Default: both. |
| `changeby` | User IDs who recorded the change, comma-separated (max 20). |
| `fields` | Fields to return, comma-separated. assetnum and siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100). |

**Não criar `authapp` nem `authsigoption`**: toda variável vira parâmetro da
ferramenta. A permissão (ASSET/READ) é checada no código.

### Passo 3 do wizard – código

Colar **todo** o `QUERYASSETDOWNTIME.py` em Source Code. **Create**. Se der erro de
compilação: copiar a mensagem exata e parar (não corrigir no Maximo).

## 2. Response Schema

Aba Main, campo **Response Schema**: colar `response_schema.json`. **Save**.

## 3. Publicar como ferramenta MCP

**More Actions → Add/Modify MCP Tool**.

| Campo | Valor |
|---|---|
| Title | `Query asset downtime history` (digitar) |
| Processing notes | `Pass date_from and date_to, except when looking up specific assetnums or wonums (full history, dates optional). Use "*" for unused parameters. "total" counts up/down changes, not assets. If "has_more" is true, request the next page or narrow the filters.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

**OK** e **Save**.

## 4. Conferir no Manage

`https://<host-do-manage>/maximo/api/oas?aitools=1`, com Ctrl+F:

- [ ] `script_queryassetdowntime` aparece.
- [ ] **`u200b` não aparece** no trecho de `/script_queryassetdowntime`.
- [ ] `authapp` e `authsigoption` não aparecem.
- [ ] 12 parâmetros no `requestBody`.

## 5. Conferir no MCP Server

O pod lê a lista a cada 10 min. **Não** reiniciar o pod. Depois de 10 min, me avisar:
eu chamo a ferramenta pelo cliente MCP.

## 6. Testes (feitos por mim via MCP; para referência)

1. `{"date_from": "2026-01-01", "date_to": "2026-10-31", "page_size": "5"}` → `total`
   e 5 itens; `downtime` nas linhas com `isrunning` verdadeiro.
2. `{"assetnums": "<ativo com paradas>"}` → histórico completo, em ordem.
3. Mesmo período com `event=down`, `code` ou `location` → só essas mudanças.
4. `{"date_from": "2026-01-01"}` → `required` em `date_to`.
5. `fields` = `orgid,assetstatusid,calnum` → sem `internal_error`.
6. 366 dias sem `siteid` → anotar o tempo.

Log (DEBUG): linha `QUERYASSETDOWNTIME implicit vars: [...]; param sources: {...}`.
SQL lento (mais de 1 s) aparece como `BMXAA6720W`: me mandar a linha.

## 7. Fechar

- **Log Level** do script para `ERROR`. Save.
- Me avisar o commit instalado.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| Erro de compilação no Create | Copiar a mensagem; não editar no Maximo. |
| `u200b` no OAS | Apagar a variável (ou o script) e recriar digitando o nome. |
| `internal_error` | Log do Manage: `QUERYASSETDOWNTIME failed: ...` (ex.: coluna inexistente). Me enviar. |
| `not_authorized` | Usuário da `apikey` sem READ em ASSET, ou sem site autorizado. |
| `total` = 0 com certeza de haver paradas | Me enviar a linha de SQL do log (autoscript em DEBUG). |
| Lento | Me mandar `BMXAA6720W` e os índices da ASSETSTATUS. |
