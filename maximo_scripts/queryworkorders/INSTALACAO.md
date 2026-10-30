# Instalação do QUERYWORKORDERS no Maximo (passo a passo)

Ambiente: homologação Itambé (MAS 9.2, Maximo Manage). Tempo estimado: 30 min + até
10 min de polling do MCP Server.

Regra do projeto: o conteúdo colado no Maximo é **exatamente** o do repositório. Se
precisar mudar algo, muda aqui primeiro e cola de novo.

## Atenção: caracteres invisíveis

Na 1ª instalação (2026-10-22) o nome do script e de 13 variáveis chegaram ao Maximo
com espaços de largura zero (U+200B) colados junto. O nome parece certo na tela,
mas é outro para o código.

- **Digitar à mão** o nome do script e os nomes das variáveis (são curtos).
- Para textos longos (código, schema, descrições), copiar do arquivo aberto no
  **editor de texto** (não do preview de markdown, do chat ou do terminal).
- O passo 5 confere isso.

## 0. Antes de começar

- Usuário com acesso ao app **Automation Scripts** (em homologação: MAXADMIN).
- Abrir no editor, para copiar:
  - `maximo_scripts/queryworkorders/QUERYWORKORDERS.py`
  - `maximo_scripts/queryworkorders/response_schema.json`
- Anotar o commit do repositório que está sendo instalado (`git log -1 --oneline`).

## Atualizar instalação existente (2026-10-30: parâmetro `text` e bloco comum)

Se o `QUERYWORKORDERS` já está instalado e funcionando, não precisa apagar e
recriar:

1. Abrir o script `QUERYWORKORDERS`.
2. Aba **Variables → New Row**, com os mesmos valores das outras (IN, LITERAL,
   ALN, `*`). Variable `text` (digitar), Description:
   `Words that must all appear in the description (max 5 words, 100 chars).`
3. Aba Main / Source Code: apagar tudo e colar **todo** o `QUERYWORKORDERS.py`
   novo. **Save**.
4. Seguir os passos 5 a 8 (agora são **15** parâmetros). Testes do `text` no passo 7.

Se aparecer `u200b` no OAS depois do passo 2, apagar só a variável e recriar
digitando o nome.

## 1. Remover a instalação anterior (se existir)

Menu → **System Configuration → Platform Configuration → Automation Scripts**.

Na aba List, filtrar por `QUERYWORKORDERS`. Se existir (inclusive com caracteres
invisíveis, como na 1ª instalação):

1. Abrir o script, desmarcar **Active?** e salvar.
2. **More Actions → Delete Script** (Excluir script). Confirmar.
3. Conferir na aba List que não sobrou nenhum `QUERYWORKORDERS`.

## 2. Criar o script (wizard)

**More Actions → Create → Script** (script sem launch point).

### Passo 1 do wizard – dados do script

| Campo | Valor |
|---|---|
| Script | `QUERYWORKORDERS` (digitar) |
| Description | `Read-only work order search: date range (YYYY-MM-DD) or wonums, filters, paging, total.` |
| Script Language | `python` (se não houver, `jython`: é o mesmo engine) |
| Log Level | `DEBUG` (só durante a validação; voltar para `ERROR` no passo 8) |
| Active? | marcado |
| Allow Invoking Script Functions? | **desmarcado** |

A Description é o que o MCP mostra como descrição da ferramenta (o long description
não aparece). Nosso agente terá descrição própria mais completa na allowlist.

Clicar **Next**.

### Passo 2 do wizard – variáveis

Criar **15 linhas** (New Row). Em todas:

- **Variable Type:** `IN`
- **Binding Type:** `LITERAL`
- **Literal Data Type:** `ALN`
- **Binding Value:** `*`

Nome **digitado em minúsculas**. Descrição em até 100 caracteres (o Maximo corta o
resto).

| Variable | Description |
|---|---|
| `date_from` | Start date, YYYY-MM-DD, inclusive. Required unless wonums is given. |
| `date_to` | End date, YYYY-MM-DD, inclusive. Max 366 days after date_from. Required unless wonums is given. |
| `date_field` | Range date: reportdate (default), statusdate, targstartdate, targcompdate, actstart, actfinish |
| `siteid` | Site IDs, comma-separated (max 20). |
| `wonums` | Work order numbers, comma-separated (max 50). Dates optional when given. |
| `status` | Status values, comma-separated (max 20), e.g. APPR,INPRG,COMP. |
| `priority` | Priority integers, comma-separated (max 20). |
| `assetnum` | Asset numbers, comma-separated (max 20). |
| `location` | Location codes, comma-separated (max 20). |
| `persongroup` | Crew/person group codes, comma-separated (max 20). |
| `worktype` | Work types, comma-separated (max 20), e.g. PM,CM,EM. |
| `text` | Words that must all appear in the description (max 5 words, 100 chars). |
| `fields` | Fields to return, comma-separated. wonum and siteid always included. |
| `page` | Page number, starting at 1 (default 1). |
| `page_size` | Items per page, 1 to 500 (default 100). |

`date_field` também aceita `schedstart` e `schedfinish` (não cabem na descrição; se o
valor for inválido, o erro lista todos).

**Não criar `authapp` nem `authsigoption`.** Toda variável vira parâmetro da
ferramenta, então quem chama poderia mandar outro valor. A permissão (WOTRACK/READ)
é checada dentro do código.

Clicar **Next**.

### Passo 3 do wizard – código

- Colar **todo** o conteúdo de `QUERYWORKORDERS.py` no campo Source Code
  (ou usar Import apontando para o arquivo).
- Clicar **Create**.

Se aparecer erro de compilação: copiar a mensagem exata e parar (não corrigir no
Maximo).

## 3. Response Schema

Abrir o script `QUERYWORKORDERS` (aba Main). No campo **Response Schema**, colar o
conteúdo de `response_schema.json`. **Save**.

## 4. Publicar como ferramenta MCP

Com o script aberto: **More Actions → Add/Modify MCP Tool**.

| Campo | Valor |
|---|---|
| Title | `Query work orders` |
| Processing notes | `Always pass date_from and date_to, except when looking up specific wonums (dates then optional). Use "*" for unused parameters. Read "total" for counts; never count items of a single page. If "has_more" is true, request the next page or narrow the filters.` |
| Read only? | marcado |
| Destructive hint? | desmarcado |
| Query API as a response? | desmarcado |
| Active? | marcado |

Se houver campo de nome MCP, deixar o padrão. Clicar **OK** e **Save**.

## 5. Conferir no Manage

No navegador logado no Manage:

```
https://<host-do-manage>/maximo/api/oas?aitools=1
```

Na resposta, com Ctrl+F:

- [ ] `script_queryworkorders` aparece.
- [ ] **`u200b` não aparece em lugar nenhum.** Se aparecer, voltar ao passo 1.
- [ ] `authapp` e `authsigoption` **não** aparecem.
- [ ] 15 parâmetros no `requestBody` (com `text`).

Me enviar o trecho de `/script_queryworkorders` se algo estiver diferente.

## 6. Conferir no MCP Server

O pod lê a lista a cada 10 min. **Não** reiniciar o pod (interrompe chamadas). Depois
de 10 min, no repositório:

```
uv run python -m maximo_agents.mcp.check_connection
```

Me enviar a saída.

## 7. Primeira chamada de teste

Pelo MCP Inspector (Transport Streamable HTTP, Connection Type Proxy, header
`apikey`), chamar a ferramenta com:

```json
{"date_from": "2026-09-01", "date_to": "2026-09-30", "page_size": "5"}
```

Esperado: JSON com `total`, `page` = 1, até 5 itens em `items`.

Depois, sem `date_to`:

```json
{"date_from": "2026-09-01"}
```

Esperado: `{"error": {"code": "required", "parameter": "date_to", ...}}`.

Busca por palavras na descrição (trocar pelas de uma OS conhecida):

```json
{"date_from": "2026-09-01", "date_to": "2026-09-30", "text": "vazamento", "page_size": "5"}
```

Esperado: só OS com a palavra na descrição; `filters.text` = `["VAZAMENTO"]`.
Depois `{"date_from": "2026-09-01", "date_to": "2026-09-30", "text": "a"}` →
`{"error": {"code": "invalid_text", ...}}`.

Me enviar as respostas (pode cortar descrições de OS se tiverem dado sensível).

Conferir também o log (logger `autoscript` / script em DEBUG): deve haver a linha
`QUERYWORKORDERS implicit vars: [...]; param sources: {...}` mostrando quais
variáveis implícitas o Maximo injetou e se os parâmetros chegaram como
`variable`, `body` ou `query`. Me enviar essa linha.

## 8. Fechar

- Voltar o **Log Level** do script para `ERROR`. Save.
- Me avisar o commit instalado para registrar na wiki.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| Erro de compilação no Create | Copiar mensagem, não editar no Maximo. |
| `u200b` no OAS | Caractere invisível colado. Apagar o script e recriar digitando os nomes. |
| Ferramenta não aparece após 10 min | Conferir Active? no script e no MCP Tool; testar `/api/oas?aitools=1`. |
| `{"error": {"code": "no_user"}}` | `request.getUserInfo()` não disponível no caminho MCP. Avisar. |
| `{"error": {"code": "not_authorized"}}` | Usuário da `apikey` sem READ em WOTRACK. |
| `{"error": {"code": "internal_error"}}` | Pegar o erro no log do Manage (`QUERYWORKORDERS failed: ...`). |
| `total` = 0 com certeza de haver OS | Me enviar a linha de log do SQL (autoscript em DEBUG). |

**Observação (2026-10-29):** em homologação, a chamada via MCP voltou com
`BMXAA10147E - O código de idioma do usuário PT é inválido para inferência` antes de
executar o script, com o usuário da `apikey` em idioma PT. `apischema` funcionou com
a mesma chave. Trocar o idioma do usuário para EN resolveu; não há confirmação de
alternativa sem mudar o usuário. Detalhes em
`memoria/wiki/entities/mas-mcp-server.md`.
