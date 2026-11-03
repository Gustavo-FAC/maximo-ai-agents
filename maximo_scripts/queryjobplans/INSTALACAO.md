# Instalação do QUERYJOBPLANS no Maximo (passo a passo)

Ambiente: homologação Itambé (MAS 9.2, Maximo Manage). Mesmo roteiro do
[QUERYWORKORDERS](../queryworkorders/INSTALACAO.md); aqui só o que muda. Tempo
estimado: 20 min + até 10 min de polling do MCP Server.

Regra do projeto: o conteúdo colado no Maximo é **exatamente** o do repositório.

**Caracteres invisíveis:** digitar à mão o nome do script e das variáveis; copiar
código, schema e descrições do arquivo aberto no editor de texto (não do preview,
chat ou terminal). O passo 5 confere `u200b`.

## 0. Antes de começar

- Usuário com acesso ao app **Automation Scripts** (em homologação: MAXADMIN).
- Usuário da `apikey` com READ no app **JOBPLAN** (Job Plans).
- Abrir no editor `maximo_scripts/queryjobplans/QUERYJOBPLANS.py` e
  `maximo_scripts/queryjobplans/response_schema.json`.
- Anotar o commit instalado (`git log -1 --oneline`).

## 1. Remover instalação anterior (se existir)

Automation Scripts → filtrar `QUERYJOBPLANS` → desmarcar **Active?**, salvar,
**More Actions → Delete Script**.

## 2. Criar o script (wizard)

**More Actions → Create → Script** (sem launch point).

### Passo 1 – dados do script

| Campo | Valor |
|---|---|
| Script | `QUERYJOBPLANS` (digitar) |
| Description | `Read-only job plan search: filters, asset links, tasks, words, paging, total.` |
| Script Language | `python` (ou `jython`) |
| Log Level | `DEBUG` (só durante a validação; voltar para `ERROR` no passo 8) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

### Passo 2 – variáveis

Criar **12 linhas**. Em todas: Variable Type `IN`, Binding Type `LITERAL`, Literal
Data Type `ALN`, Binding Value `*`. Nome digitado em minúsculas.

| Variable | Description |
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

**Não criar `authapp` nem `authsigoption`** (permissão JOBPLAN/READ checada no código).

### Passo 3 – código

Colar **todo** o `QUERYJOBPLANS.py` em Source Code → **Create**. Erro de compilação:
copiar a mensagem e parar.

## 3. Response Schema

Abrir o script (aba Main), colar `response_schema.json` em **Response Schema**, **Save**.

## 4. Publicar como ferramenta MCP

**More Actions → Add/Modify MCP Tool**:

| Campo | Valor |
|---|---|
| Title | `Query job plans` |
| Processing notes | `Use "*" for unused parameters. Read "total" for counts; never count items of a single page. If "has_more" is true, request the next page or narrow the filters.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

**OK** e **Save**.

## 5. Conferir no Manage

`https://<host-do-manage>/maximo/api/oas?aitools=1`, com Ctrl+F:

- [ ] `script_queryjobplans` aparece.
- [ ] `u200b` não aparece.
- [ ] `authapp` e `authsigoption` não aparecem.
- [ ] 12 parâmetros no `requestBody`.

## 6. Conferir no MCP Server

Após 10 min (sem reiniciar o pod):

```
uv run python -m maximo_agents.mcp.check_connection
```

## 7. Chamadas de teste

Pelo Claude Code (ferramenta `script_queryjobplans`, depois de reiniciar a sessão) ou
MCP Inspector:

```json
{"page_size": "5"}
```

Esperado: `total`, `filters.status = ["ACTIVE"]` e até 5 itens.

```json
{"page_size": "2", "include_tasks": "Y"}
```

Esperado: 2 planos, cada um com `jobplanid` e `tasks`; `tasks_truncated: false`.

```json
{"include_tasks": "talvez"}
```

Esperado: `{"error": {"code": "invalid_flag", "parameter": "include_tasks", ...}}`.

Depois, a checklist "Validar em homologação" do [README](README.md).

## 8. Fechar

Voltar **Log Level** para `ERROR`, salvar e avisar o commit instalado.

## Se algo der errado

Mesma tabela do [QUERYWORKORDERS](../queryworkorders/INSTALACAO.md#se-algo-der-errado).
Específico daqui:

- `not_authorized` = usuário da `apikey` sem READ no app JOBPLAN.
- `internal_error` sem filtro = conferir no log o SQL da autorização de site (subselect
  em SITE) e do status padrão (subselect em SYNONYMDOMAIN).
- `internal_error` só com `include_tasks` = consulta em JOBTASK (`jobplanid`).
- `internal_error` só com `description_longdescription` = leitura da descrição longa
  pelo Mbo; mandar o trecho do log.
