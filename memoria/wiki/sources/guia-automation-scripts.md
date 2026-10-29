---
title: Guia de Automation Scripts do Maximo (IBM Autoscripting Guide)
type: source
sources: [docs/Automation_Scripts_IBM_Maximo.docx]
related: [[automation-scripts-como-ferramentas]], [[mas-mcp-server]]
created: 2026-10-22
updated: 2026-10-22
---

# Guia de Automation Scripts

Tradução/resumo do IBM Maximo Autoscripting Guide
(ibm-maximo-dev.github.io/maximo-autoscript-documentation), out/2026. Arquivo em
`docs/`. Guia amplo (MBO, atributo, MIF, UI, cron); para o projeto importam as
seções 1.4, 2, 6 e 10.

## Relevante para nossas ferramentas

- Linguagens: **Jython** e **JavaScript (Nashorn)**. Compilados em bytecode e
  cacheados; mudança propaga para o cluster.
- Variáveis literais: tipo em `AUTOSCRIPTVARS.literaldatatype` — ALN, INTEGER,
  SMALLINT, DECIMAL, YORN, DATETIME, FLOAT. Não há tipo lista.
- Script REST (6.1): `/maximo/api/script/<NOME>`; variáveis `request`
  (`getQueryParam`, `getUserInfo`), `requestBody`, `responseBody`,
  `responseHeaders`.
- **Segurança (6.1): por padrão qualquer usuário autenticado chama qualquer script
  via REST.** Restringir por script com variáveis literais `authapp` e
  `authsigoption`.
- Query segura (6.3): `SqlFormat` com `setObject(n, "WORKORDER", "ATTR", valor)`
  e `mboset.setUserWhere(...)`. Padrão `*` para parâmetro não informado.
- Log: `service.log_*` (tempo real); logger com nome do script.
- Teste: botão Test do app Automation Scripts (pode fazer commit em alguns casos).

## Boas práticas que viram regra nossa

- `MboSet.count()` dispara SQL a cada chamada: chamar **uma vez**.
- Sets criados via `MXServer.getMboSet(...)`: **`cleanup()` em `finally`**
  (senão OutOfMemory).
- Script roda na thread do Maximo: script lento pesa em todos.
- ~~`service.isLoggingEnabled()` antes de log caro.~~ **Errado no MAS 9.2 da
  Itambé** (2026-10-29): `ScriptService` não tem esse método (AttributeError). Usar
  `service.log_debug(...)` direto; o nível do logger filtra.
