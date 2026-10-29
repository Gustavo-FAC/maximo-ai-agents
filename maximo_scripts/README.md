# Automation scripts do Maximo

Cópia oficial (fonte) dos automation scripts instalados no Maximo Manage dos clientes
e publicados como ferramentas no MCP Server.

Regras:

- Todo script nasce e é alterado aqui, nunca direto no Maximo.
- Nomes, descrições e parâmetros em inglês, com response schema definido.
- Somente consulta: nenhum script altera dados no Maximo.
- Intervalo de datas obrigatório em consultas de movimento (OS, falhas, medições),
  com paginação e limite de registros. Cadastro (ativos) não exige data (decisão
  2026-10-29); a página limita a resposta.

Convenções:

- Uma pasta por script (`maximo_scripts/<nome>/`) com o script, `response_schema.json`
  e `README.md` (descrição da ferramenta, variáveis, registro, validação).
- Linguagem **Jython 2.7**. O código precisa rodar também em CPython 3 para os testes
  em `tests/unit/`: sem f-string, sem `super()` sem argumentos, sem `raise ... from`,
  arquivo só em ASCII. Imports Java/Maximo apenas dentro de funções de runtime.
- Texto com `"%s" % (valor,)`, nunca `str(valor)` (quebra com acento no Jython).
- Filtros sempre por bind (`SqlFormat`); colunas só de listas fixas.
- `MboSet`: `count()` uma vez, `cleanup()` em `finally`.
- Código compartilhado copiado entre `# --- BEGIN COMMON` e `# --- END COMMON ---`,
  igual em todos os scripts (sem script biblioteca). `tests/unit/test_script_common.py`
  confere o bloco e as regras acima (ASCII, imports, `globals()`, sem escrita).

Scripts:

- [`queryworkorders/`](queryworkorders/README.md) – consulta genérica de OS
  (ainda sem o bloco comum; entra junto com o parâmetro `text`).
- [`queryassets/`](queryassets/README.md) – consulta genérica de ativos.
