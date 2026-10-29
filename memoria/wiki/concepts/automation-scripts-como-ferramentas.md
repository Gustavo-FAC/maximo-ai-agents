---
title: Automation scripts como ferramentas
type: concept
sources: [docs/Maximo MCP Server — Documentação.docx, docs/Automation_Scripts_IBM_Maximo.docx]
related: [[mas-mcp-server]], [[itambe-cimentos]], [[allowlist-somente-leitura]], [[doc-mcp-server]], [[guia-automation-scripts]]
created: 2026-10-21
updated: 2026-10-29
---

# Automation scripts como ferramentas

Ferramentas de dados são automation scripts no Maximo, publicados no
[[mas-mcp-server]]. Fonte oficial em `maximo_scripts/`; nunca editar direto no Maximo.

## Regras

- Somente consulta. Nomes, descrições e parâmetros em inglês, com response schema.
- Parâmetros: intervalo de datas (obrigatório, com limite; **dispensado só com lista
  de wonum**, decisão do usuário 2026-10-29: OS antiga sem data conhecida; **cadastro (ativos) não exige data**, decisão do usuário 2026-10-29), campo de data, site,
  lista de wonum (com limite), status, prioridade, ativo, local, equipe, tipo de
  trabalho, paginação com total de registros, seleção de campos.

## Respostas (2026-10-22, de [[doc-mcp-server]] e [[guia-automation-scripts]])

- **Registro:** script sem launch point → descrição em inglês → response schema →
  Active? → More Actions > Add/Modify MCP Tool (título, notas, flags). Aparece no
  próximo polling (10 min).
- **Parâmetros:** uma variável por parâmetro, binding Literal, tipo em
  `literaldatatype` (ALN, INTEGER, DATETIME…). Listas (wonum, status) vão como ALN
  separado por vírgula e o script divide.
- **Resposta:** JSON via `responseBody = OslcUtils.jsonToBytes(jo)`.
- **Linguagem:** Jython (exemplos IBM em Jython). JS/Nashorn também funciona.

## Regras de implementação (derivadas)

- Consulta com `MXServer.getMboSet("WORKORDER", userInfo)` do usuário da chamada
  → herda segurança de site/dados do Maximo.
- Filtros só via `SqlFormat.setObject` (nunca concatenar valor no where).
- `count()` uma vez para o total; `cleanup()` em `finally`.
- Validar limites no script: intervalo de datas máximo, tamanho da lista de wonum,
  `page_size` máximo. O agente não é confiável para respeitar limites.
- Declarar `authapp` / `authsigoption` (ex.: WOTRACK + READ) para exigir permissão
  de leitura de OS.
- Flag **Read only?** marcada, mas sem confiar nela (ver
  [[allowlist-somente-leitura]]).

## Perguntas abertas (testar no primeiro script)

- Parâmetro opcional: o schema gerado pelo MCP marca todas as variáveis como
  obrigatórias? Como passar "vazio"?
- Como DATETIME chega pelo MCP (formato ISO aceito?).
- `userInfo` disponível no script chamado via MCP: `request.getUserInfo()` existe
  nesse caminho? É o dono da `apikey`?
- `authapp`/`authsigoption` também valem no caminho MCP?

## Estado

- 2026-10-22: `QUERYWORKORDERS` escrito em `maximo_scripts/queryworkorders/` (Jython
  2.7, testes da lógica pura em CPython). **Ainda não instalado no Maximo.** Checklist
  de validação no README do script responde as perguntas abertas acima.
- Variáveis `authapp`/`authsigoption` podem virar parâmetro da ferramenta no MCP:
  conferir na instalação (risco de o chamador sobrescrever).
- Jython 2.7: `str()` quebra com acento; usar `"%s" % (v,)`. Fonte só ASCII.
- 2026-10-29: reinstalado em homologação. OAS conferido contra o repositório:
  14 parâmetros iguais a `PARAM_NAMES`, 12 chaves de resposta iguais a
  `response_schema.json`, sem `u200b`, sem `authapp`/`authsigoption`. Nenhum
  parâmetro marcado como obrigatório (o script valida). Execução real ainda **não
  testada**: chamada via MCP recusada com BMXAA10147E (idioma PT do usuário), ver
  observação em [[mas-mcp-server]]. Perguntas abertas acima seguem abertas.
- 2026-10-29: com usuário em EN, o script rodou e falhou em
  `ImportError: No module named datetime` (linha 10). **O Jython do Maximo não traz
  a biblioteca padrão do Python.** Regra: nada de `import` Python nos scripts, só
  Java/Maximo. Datas agora em classe `Day` própria (algoritmo civil de Hinnant),
  conferida dia a dia contra `datetime` de 1900 a 2100 no teste; outro teste
  barra imports fora de `java`/`psdi`/`com`. 43 testes.
- 2026-10-29: reinstalado sem `datetime` → sem erro, mas a resposta MCP veio com
  **todas as chaves do response schema em `null`**, inclusive no caso de erro. O MCP
  não recebeu nosso JSON. Hipóteses: (1) `request` não é injetado no caminho MCP e o
  bloco `if "request" in globals()` não rodava; (2) `responseBody` como String em
  vez de `OslcUtils.jsonToBytes(jo)`. Correção cobrindo as duas: runtime detectado
  por `from java.lang import System`, variáveis implícitas lidas do escopo,
  identidade por `request.getUserInfo()` ou, sem `request`, `userInfo` implícito
  (falha fechado se nenhum), `responseBody = OslcUtils.jsonToBytes(...)`, log DEBUG
  com as variáveis implícitas presentes.
- 2026-10-29 14:05: essa versão reinstalada deu HTTP 500 BMXAA1649E
  (NullPointerException) em ~7 s, também na chamada sem `date_to` (caminho que só
  valida e monta JSON de erro). Suspeita: saída da resposta (`jsonToBytes` ou o
  tratamento de bytes no caminho `?ccm=1`). **Falta stack trace do log do Manage**
  (pod `itambe-integration`).
- 2026-10-29 (chave nova): mesmo BMXAA1649E. Correção: a chamada sem `date_to` **não**
  só valida: `run()` consulta APPLICATIONAUTH antes, com `SqlFormat(where)` sem
  `UserInfo` (sem locale/fuso para `setObject`). Agora `SqlFormat(user_info, ...)`
  nas duas consultas e `except (Exception, Throwable)` para exceção Java não escapar
  sem log. Se o NPE persistir com o log `QUERYWORKORDERS failed` ausente, culpado é
  `jsonToBytes`/saída. Falta reinstalar.
- 2026-10-29 (log do Manage): **causa real do BMXAA1649E.** O script terminava
  (~3,4 s), depois `JSR223ScriptDriver.copyFromBindings` chama `String.valueOf` em
  **toda variável de topo** (e `ScriptBinding.get` loga em DEBUG). `_scope = globals()`
  no topo guardava o próprio escopo → `PyScriptEngineScope.toString` ↔
  `PyDictionary.toString` recursivo → `java.lang.StackOverflowError`. A hipótese do
  `SqlFormat` não era a causa do 500 (correção mantida). Correção: lógica em
  `_main(scope, throwable)`; no topo só `responseBody`.
  **Regra:** nenhuma variável de topo pode referenciar `globals()`/escopo; preferir
  locais de função (cada variável de topo é copiada e convertida em texto). Teste
  com `ast` barra `x = globals()` no topo. 44 testes. Falta reinstalar.
- 2026-10-29 11:42: reinstalado → **sem HTTP 500**; MCP entrega nosso JSON
  (`internal_error`). Log: `'ScriptService' object has no attribute
  'isLoggingEnabled'` (o guia indicava esse método). Removido; `log_debug` direto.
- 2026-10-29: **funcionando via MCP** (Claude Code, chave MAXADMIN de homologação).
  Conferido: jan/2026 → `total` 3900, paginação (`page`, `total_pages`, `has_more`);
  filtros `status`+`worktype`, `wonums`, `siteid`, `date_field=actfinish` (fim
  inclusivo), `fields`; sem parâmetros → `required`/`date_from`; 2 anos →
  `range_too_large`; `page_size=1000` → `out_of_range`. Acento ok ("REVISÃO").
  `siteid` vem sempre, mesmo fora de `fields`.

## Respostas do runtime (2026-10-29)

- Parâmetro opcional: omitido no MCP chega vazio; o script valida. OK.
- DATETIME: parâmetros ALN `YYYY-MM-DD` + `SqlFormat.setTimestamp` funcionam.
- Identidade: `request.getUserInfo()` ou `userInfo` funcionam no caminho MCP; qual
  dos dois e a origem dos parâmetros ficam na linha DEBUG `implicit vars` (pendente).
- `authapp`/`authsigoption`: não usados; permissão checada no código.
- Jython do Maximo: sem biblioteca padrão; `ScriptService` sem `isLoggingEnabled`;
  toda variável de topo é convertida em texto após a execução (nada de `globals()`
  em variável de topo; lógica em função).
- Teste da segurança de site com usuário sem acesso: pendente (chave de gerente).

## Aprendido no OAS da 1ª instalação (2026-10-22)

`/api/oas?aitools=1` mostra a ferramenta como `/script_<nome>` (`toolType: AUTOSCRIPT`).

- **Toda variável vira parâmetro** do `requestBody`, inclusive `authapp` e
  `authsigoption`. Logo, segurança nunca em variável: checar permissão no código.
- Nenhum parâmetro sai como obrigatório; todos `string` (ALN).
- Descrição da ferramenta = campo **Description** do script (curto). Long
  description não aparece. Descrição de variável cortada em **100 caracteres**.
- Colagem no Maximo trouxe **U+200B** (espaço de largura zero) no nome do script e
  de 13 variáveis. Digitar nomes à mão; conferir `u200b` no OAS.
- Consequência para o nosso lado: a [[allowlist-somente-leitura]] deve guardar
  descrição própria (rica) das ferramentas e rejeitar nomes com caractere não ASCII.
