# Instalação do QUERYSRS no Maximo (passo a passo)

Ambiente: homologação Itambé (MAS 9.2, Maximo Manage). Mesmo roteiro do
[QUERYWORKORDERS](../queryworkorders/INSTALACAO.md); aqui só o que muda. Tempo
estimado: 30 min + até 10 min de polling do MCP Server.

Regra do projeto: o conteúdo colado no Maximo é **exatamente** o do repositório.

**Caracteres invisíveis:** digitar à mão o nome do script e das variáveis; copiar
código, schema e descrições do arquivo aberto no editor de texto (não do preview,
chat ou terminal). O passo 5 confere `u200b`.

## 0. Antes de começar

- Usuário com acesso ao app **Automation Scripts** (em homologação: MAXADMIN).
- Usuário da `apikey` com READ no app **SR** (Service Requests) e idioma EN
  (BMXAA10147E).
- Abrir no editor `maximo_scripts/querysrs/QUERYSRS.py` e
  `maximo_scripts/querysrs/response_schema.json`.
- Anotar o commit instalado (`git log -1 --oneline`).

## 1. Criar o script (wizard)

Automation Scripts → **More Actions → Create → Script** (sem launch point).

| Campo | Valor |
|---|---|
| Script | `QUERYSRS` (digitar) |
| Description | `Read-only service request (SR) search: date range or ticketids, filters, paging, total.` |
| Script Language | `python` (se não houver, `jython`) |
| Log Level | `DEBUG` (só durante a validação) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

**Next.** Criar **18 variáveis** (New Row), todas **IN**, **LITERAL**, **ALN**,
Binding Value `*`, nome digitado em minúsculas. Nomes e descrições: tabela
"Variáveis" do [README](README.md) (copiar do arquivo no editor).

**Não criar `authapp` nem `authsigoption`** (a permissão é checada no código).

**Next.** Colar **todo** o `QUERYSRS.py` em Source Code. **Create**. Erro de
compilação: copiar a mensagem e parar.

## 2. Response Schema

Abrir o script (aba Main), colar `response_schema.json` em **Response Schema**. **Save**.

## 3. Publicar como ferramenta MCP

**More Actions → Add/Modify MCP Tool**:

| Campo | Valor |
|---|---|
| Title | `Query service requests` |
| Processing notes | `Always pass date_from and date_to, except when looking up specific ticketids. Use "*" for unused parameters. Read "total" for counts; never count items of a single page. If "has_more" is true, request the next page or narrow the filters.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

**OK** e **Save**.

## 4. Liberar no Claude Code

Nada a fazer: `script_querysrs` já está na allowlist do repositório
(`src/maximo_agents/mcp/allowlist.py`), que o hook `claude_code_guard.py` usa.

## 5. Conferir no Manage e no MCP

- `https://<host-do-manage>/maximo/api/oas?aitools=1`: `script_querysrs` aparece,
  **18** parâmetros, sem `u200b`, sem `authapp`/`authsigoption`.
- Depois de 10 min: `uv run python -m maximo_agents.mcp.check_connection`.

## 6. Chamadas de teste

Um mês, para ver status e grupos em uso:

```json
{"date_from": "2026-03-01", "date_to": "2026-03-31", "fields": "status,ownergroup,owner", "page_size": "20"}
```

Esperado: `total` igual ao app SR com o mesmo filtro (sites autorizados).

Uma SR conhecida (trocar `<SR>`), com histórico e OS geradas:

```json
{"ticketids": "<SR>", "include_history": "Y", "include_workorders": "Y"}
```

Esperado: `history` com as mudanças de status (mais antiga primeiro), `workorders`
com as OS criadas a partir dela (ou `[]`), `history_truncated` e
`workorders_truncated` = `false`.

Erro esperado: `{"date_from": "2026-03-01"}` →
`{"error": {"code": "required", "parameter": "date_to", ...}}`.

Me enviar as respostas. Conferir também se há SR **sem site** no app SR (filtro
Site vazio): essas não voltam pela ferramenta.

## 7. Fechar

Log Level `ERROR`, **Save**. Me avisar o commit instalado.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| `not_authorized` | Usuário da `apikey` sem READ no app SR. |
| `internal_error` | Erro no log do Manage (`QUERYSRS failed: ...`). Avisar. |
| `include_history` dá erro | Mandar a linha do log: relação ad hoc `$QSRSTATUS` no TKSTATUS. |
| `total` 0 com SR existente | Ver se a SR tem site; mandar a linha de SQL do log (DEBUG). |
