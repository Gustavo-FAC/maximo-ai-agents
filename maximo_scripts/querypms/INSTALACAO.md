# Instalação do QUERYPMS no Maximo (passo a passo)

Ambiente: homologação Itambé (MAS 9.2, Maximo Manage). Mesmo roteiro do
[QUERYWORKORDERS](../queryworkorders/INSTALACAO.md); aqui só o que muda. Tempo
estimado: 20 min + até 10 min de polling do MCP Server.

Regra do projeto: o conteúdo colado no Maximo é **exatamente** o do repositório.

**Caracteres invisíveis:** digitar à mão o nome do script e das variáveis; copiar
código, schema e descrições do arquivo aberto no editor de texto (não do preview,
chat ou terminal). O passo 5 confere `u200b`.

## 0. Antes de começar

- Usuário com acesso ao app **Automation Scripts** (em homologação: MAXADMIN).
- Usuário da `apikey` com READ no app **PM** (Preventive Maintenance) e idioma **EN**.
- Abrir no editor `maximo_scripts/querypms/QUERYPMS.py` e
  `maximo_scripts/querypms/response_schema.json`.
- Anotar o commit instalado (`git log -1 --oneline`).

## 1. Remover instalação anterior (se existir)

Automation Scripts → filtrar `QUERYPMS` → desmarcar **Active?**, salvar,
**More Actions → Delete Script**.

## 2. Criar o script (wizard)

**More Actions → Create → Script** (sem launch point).

### Passo 1 – dados do script

| Campo | Valor |
|---|---|
| Script | `QUERYPMS` (digitar) |
| Description | `Read-only PM search: due date range, asset, location, filters, paging, total.` |
| Script Language | `python` (ou `jython`) |
| Log Level | `DEBUG` (só durante a validação; voltar para `ERROR` no passo 8) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

### Passo 2 – variáveis

Criar **15 linhas**, nesta ordem. Em todas: Variable Type `IN`, Binding Type
`LITERAL`, Literal Data Type `ALN`, Binding Value `*`. Nome digitado em minúsculas.

| Variable | Description |
|---|---|
| `due_from` | Earliest due date (extdate or nextdate), YYYY-MM-DD, inclusive. Optional. |
| `due_to` | Latest due date, YYYY-MM-DD, inclusive. Optional; alone: everything due up to it. |
| `siteid` | Site IDs, comma-separated (max 20). |
| `pmnums` | PM numbers, comma-separated (max 50). |
| `status` | PM status values (max 20). Default: active only. ALL: every status. |
| `assetnum` | Asset numbers, comma-separated (max 20). |
| `location` | Location codes, comma-separated (max 20). |
| `jpnum` | Job plan numbers, comma-separated (max 20). |
| `worktype` | Work types, comma-separated (max 20). |
| `crewid` | Crew IDs, comma-separated (max 20). |
| `persongroup` | Person group (work group) codes, comma-separated (max 20). |
| `text` | Words that must all appear in the description (max 5 words, 100 chars). |
| `fields` | Fields to return, comma-separated. pmnum and siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100); max 50 with long description. |

**Não criar `authapp` nem `authsigoption`** (permissão PM/READ checada no código).

### Passo 3 – código

Colar **todo** o `QUERYPMS.py` em Source Code → **Create**. Erro de compilação:
copiar a mensagem e parar.

## 3. Response Schema

Abrir o script (aba Main), colar `response_schema.json` em **Response Schema**, **Save**.
Sem ele o MCP corta `due_from`, `due_to` e outras chaves da resposta.

## 4. Publicar como ferramenta MCP

**More Actions → Add/Modify MCP Tool**:

| Campo | Valor |
|---|---|
| Title | `Query preventive maintenance` |
| Processing notes | `Use "*" for unused parameters. Read "total" for counts; never count items of a single page. If "has_more" is true, request the next page or narrow the filters.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

**OK** e **Save**.

## 5. Conferir no Manage

`https://<host-do-manage>/maximo/api/oas?aitools=1`, com Ctrl+F:

- [ ] `script_querypms` aparece.
- [ ] `u200b` não aparece.
- [ ] `authapp` e `authsigoption` não aparecem.
- [ ] 15 parâmetros no `requestBody`.

## 6. Conferir no MCP Server

Após 10 min (sem reiniciar o pod):

```
uv run python -m maximo_agents.mcp.check_connection
```

## 7. Chamadas de teste

Pelo Claude Code (ferramenta `script_querypms`, depois de reiniciar a sessão) ou MCP
Inspector:

```json
{"page_size": "5"}
```

Esperado: `total`, `filters.status = ["ACTIVE"]`, até 5 PMs com `due_date`.

```json
{"due_from": "2026-11-15", "due_to": "2026-11-21", "page_size": "10"}
```

Esperado: só PMs com `due_date` de 15 a 21/11; `due_from` e `due_to` na resposta.

```json
{"pmnums": "<uma PM>", "fields": "description,modalidade"}
```

Esperado: `modalidade` preenchida.

```json
{"due_from": "2026-11-21", "due_to": "2026-11-15"}
```

Esperado: `{"error": {"code": "invalid_range", "parameter": "due_to", ...}}`.

Depois, a checklist "Validar em homologação" do [README](README.md).

## 8. Fechar

Voltar **Log Level** para `ERROR`, salvar e avisar o commit instalado.

## Se algo der errado

Mesma tabela do [QUERYWORKORDERS](../queryworkorders/INSTALACAO.md#se-algo-der-errado).
Específico daqui:

- `not_authorized` = usuário da `apikey` sem READ no app PM.
- `internal_error` só com `due_from`/`due_to` = `coalesce(extdate, nextdate)` no SQL;
  mandar o trecho do log.
- `internal_error` só com `modalidade` = leitura do dicionário de dados
  (`getMaximoDD`); mandar o trecho do log.
