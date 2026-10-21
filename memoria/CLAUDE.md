# Memória do projeto – esquema (padrão Memoriki / LLM Wiki)

Base de conhecimento do projeto mantida pelo LLM, no padrão
[Memoriki](https://github.com/AyanbekDos/memoriki) (LLM Wiki do Karpathy + MemPalace).

## Estrutura

```
memoria/
  CLAUDE.md          # Este esquema
  mempalace.yaml     # Config do MemPalace (opcional, busca semântica via MCP)
  raw/               # Fontes imutáveis (atas, guias, docs do cliente). Fora do git.
  wiki/              # Wiki gerada pelo LLM (o LLM é dono)
    index.md         # Catálogo de páginas, atualizado a cada alteração
    log.md           # Registro cronológico (só acrescentar)
    entities/        # Clientes, sistemas, produtos, ferramentas
    concepts/        # Decisões, padrões, regras
    sources/         # Resumo de cada fonte de raw/
    synthesis/       # Análises transversais, estado do projeto
```

## Regras

1. **Nunca alterar arquivos em `raw/`.**
2. **Sempre atualizar `wiki/index.md`** ao criar ou alterar página.
3. **Sempre acrescentar em `wiki/log.md`** após cada operação.
4. Ligar páginas com `[[nome-da-pagina]]`.
5. Toda página tem frontmatter YAML:
   ```yaml
   ---
   title: Título
   type: entity|concept|source|synthesis
   sources: [arquivos de raw/ usados]
   related: [[paginas-ligadas]]
   created: AAAA-MM-DD
   updated: AAAA-MM-DD
   ---
   ```
6. Formato do log: `## [AAAA-MM-DD] operação | Descrição`
7. **Nenhum segredo na wiki** (chaves, senhas, URLs com token). Só nomes de variáveis.
8. O `CLAUDE.md` da raiz prevalece; a wiki registra contexto e histórico, não muda decisões.

## Operações

- **Início de sessão:** ler `wiki/index.md` e `wiki/synthesis/estado-do-projeto.md`.
- **Fim de sessão:** atualizar `estado-do-projeto.md`, páginas afetadas, índice e log.
- **Ingest:** fonte nova em `raw/` → resumo em `sources/`, atualizar entidades e
  conceitos, índice e log.
- **Query:** ler índice, ler páginas, responder citando páginas; se valer, salvar em
  `synthesis/`.
- **Lint:** contradições, páginas órfãs, conceitos sem página, informação velha.

## Idioma

Wiki em português (idioma do projeto). Nomes técnicos do Maximo em inglês.
