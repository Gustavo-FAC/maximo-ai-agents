# Instalação do QUERYASSETS no Maximo (passo a passo)

Ambiente: homologação Itambé (MAS 9.2, Maximo Manage). Mesmo roteiro do
[QUERYWORKORDERS](../queryworkorders/INSTALACAO.md); aqui só o que muda. Tempo
estimado: 20 min + até 10 min de polling do MCP Server.

Regra do projeto: o conteúdo colado no Maximo é **exatamente** o do repositório.

**Caracteres invisíveis:** digitar à mão o nome do script e das variáveis; copiar
código, schema e descrições do arquivo aberto no editor de texto (não do preview,
chat ou terminal). O passo 5 confere `u200b`.

## 0. Antes de começar

- Usuário com acesso ao app **Automation Scripts** (em homologação: MAXADMIN).
- Abrir no editor `maximo_scripts/queryassets/QUERYASSETS.py` e
  `maximo_scripts/queryassets/response_schema.json`.
- Anotar o commit instalado (`git log -1 --oneline`).

## 1. Remover instalação anterior (se existir)

Automation Scripts → filtrar `QUERYASSETS` → desmarcar **Active?**, salvar,
**More Actions → Delete Script**.

## 2. Criar o script (wizard)

**More Actions → Create → Script** (sem launch point).

### Passo 1 – dados do script

| Campo | Valor |
|---|---|
| Script | `QUERYASSETS` (digitar) |
| Description | `Read-only asset search: filters, hierarchy, description words, paging, total.` |
| Script Language | `python` (ou `jython`) |
| Log Level | `DEBUG` (só durante a validação; voltar para `ERROR` no passo 8) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

### Passo 2 – variáveis

Criar **13 linhas**. Em todas: Variable Type `IN`, Binding Type `LITERAL`, Literal
Data Type `ALN`, Binding Value `*`. Nome digitado em minúsculas.

| Variable | Description |
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

**Não criar `authapp` nem `authsigoption`** (permissão ASSET/READ checada no código).

### Passo 3 – código

Colar **todo** o `QUERYASSETS.py` em Source Code → **Create**. Erro de compilação:
copiar a mensagem e parar.

## 3. Response Schema

Abrir o script (aba Main), colar `response_schema.json` em **Response Schema**, **Save**.

## 4. Publicar como ferramenta MCP

**More Actions → Add/Modify MCP Tool**:

| Campo | Valor |
|---|---|
| Title | `Query assets` |
| Processing notes | `Use "*" for unused parameters. Read "total" for counts; never count items of a single page. If "has_more" is true, request the next page or narrow the filters.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

**OK** e **Save**.

## 5. Conferir no Manage

`https://<host-do-manage>/maximo/api/oas?aitools=1`, com Ctrl+F:

- [ ] `script_queryassets` aparece.
- [ ] `u200b` não aparece.
- [ ] `authapp` e `authsigoption` não aparecem.
- [ ] 13 parâmetros no `requestBody`.

## 6. Conferir no MCP Server

Após 10 min (sem reiniciar o pod):

```
uv run python -m maximo_agents.mcp.check_connection
```

## 7. Chamadas de teste

Pelo Claude Code (ferramenta `script_queryassets`) ou MCP Inspector:

```json
{"page_size": "5"}
```

Esperado: `total` e até 5 itens.

```json
{"text": "a"}
```

Esperado: `{"error": {"code": "invalid_text", "parameter": "text", ...}}`.

Depois, a checklist "Validar em homologação" do [README](README.md).

## 8. Fechar

Voltar **Log Level** para `ERROR`, salvar e avisar o commit instalado.

## Se algo der errado

Mesma tabela do [QUERYWORKORDERS](../queryworkorders/INSTALACAO.md#se-algo-der-errado).
Específico daqui: `not_authorized` = usuário da `apikey` sem READ no app ASSET;
`internal_error` com `ancestor` = conferir no log o SQL do subselect em ASSETANCESTOR.
