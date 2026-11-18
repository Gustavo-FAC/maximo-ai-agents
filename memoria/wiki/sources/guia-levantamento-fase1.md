---
title: Guia de levantamento – Fase 1 (Itambé, preenchido)
type: source
sources: [raw/guia-levantamento-fase1-itambe-2026-11-16.docx]
related: [[itambe-cimentos]], [[ferramentas-maximo]], [[prompts-de-teste]], [[estado-do-projeto]]
created: 2026-11-17
updated: 2026-11-17
---

# Guia de levantamento – Fase 1 (Itambé)

Preenchido em 16/11/2026 pelo consultor funcional com o gerente. Recebido em
2026-11-17. Original em `raw/` (fora do git; tem nome e e-mail do gerente). Respostas
do cliente: **contexto, não muda decisão de arquitetura sozinho**; conflitos abaixo
precisam de confirmação.

## 1. Cliente

Cimento; ~3000 OS/mês; usa Maximo há 20 anos.

## 2. Perguntas do gerente (17) → cobertura

"Posição" = location. "MP" = preventiva (registro PM). "SS" = solicitação de serviço.

| Nº | Pergunta (resumida) | Freq. | Hoje | Cobertura atual |
|---|---|---|---|---|
| 1 | MPs vencendo esta semana | semanal | Power BI | **falta**: `QUERYPMS` (`nextdate`) |
| 2 | Existe MP para posição/ativo? | esporádica | Maximo | **falta**: `QUERYPMS` |
| 3 | Última MP gerada para posição/ativo | esporádica | Maximo | **falta**: `pmnum` no `QUERYWORKORDERS` ou `QUERYPMS` (`laststartdate`) |
| 4 | OS vencidas por equipe, setor, ativo ou posição | semanal | Power BI | `analyze_overdue_work_orders` (2026-11-18; com e sem tolerância; falta dado real); "setor" = qual campo? |
| 5 | Última OS executada para ativo/posição | mensal | Maximo | ok: `QUERYWORKORDERS` por `actfinish` |
| 6 | OS designadas para um colaborador | semanal | Power BI | **falta**: filtro `lead` ou designação (ASSIGNMENT)? |
| 7 | % OS emitidas × executadas no mês por equipe | mensal | Power BI | **falta**: análise nova (equipe = `crewid`) |
| 8 | % OS executadas por modalidade | mensal | Power BI | **falta**: campo `MODALIDADE` (customizado) |
| 9 | Dados de especificação de um equipamento | esporádica | Maximo | ok: `QUERYASSETS include_specs` |
| 10 | Quantos equipamentos com tal especificação (motor 50 CV) | esporádica | Maximo | **falta**: filtro por spec no `QUERYASSETS` |
| 11 | Última quebra/falha de um equipamento | esporádica | Maximo | parcial: OS corretivas do ativo (tipos a confirmar) |
| 12 | Quantas vezes o equipamento teve tal falha no período | esporádica | Maximo | parcial: `text` + reincidência; sem classe de falha |
| 13 | SS pendentes por grupo proprietário | mensal | Power BI | **falta**: script de SS |
| 14 | Status / tratativa de uma SS | esporádica | Power BI | **falta**: script de SS |
| 15-17 | Equipamentos em manutenção externa (módulo de SS): quais, há quantos dias, por fornecedor | mensal | Power BI | **falta**: script de SS; entender o módulo |

## 3. Status (visão do gerente)

| Status | Significado | Grupo | Backlog? |
|---|---|---|---|
| APROG | Aguardando programação pela equipe | Aberta | Não |
| AGENV | Aguardando envio para equipe responsável | Aguardando | Não |
| AGEXEC | Aguardando execução | Em execução | Sim |
| AGEXECFIL | OS pai aguardando filhas | Em execução | Sim |
| OSFILENC | Filhas encerradas | Concluída | Sim |
| AGINSP | Aguardando inspeção | Em execução | Sim |
| EMAND | Em andamento | Em execução | Sim |
| PREVCAN | Preventiva cancelada | Cancelada | Não |
| DEVPCM | Devolvida ao PCM para programação | Aberta | Não |
| CONCL | Concluído | Concluída | Sim (?) |
| FECHAR | Fechado | Fechado | Sim (?) |
| WMATL | Aguardando material | Aguardando | Sim |

Fora da lista: AAPROV, APRV, ACONDF, INPRG, POSEXEC, COMP, CANCEL, EDITHIST.

## 4. Datas e atraso

- "OS de outubro" = data de **abertura** (`reportdate`, já é o padrão).
- Atrasada: passou da data de previsão e não foi executada. Campo: **"Início
  Previsto"** (a confirmar se é `targstartdate` ou `schedstart`). Sem data limite:
  não conta. **Tolerância: 7 dias.** Semana começa no **domingo**. Mês calendário.
  Fuso: "nenhum".

## 5. Prioridades e tipos

Prioridade (1 = mais alta): 1 Urgente (1 dia), 2 Alto (7 dias), 3 Médio (15 dias),
4 Baixo (30 dias).

| Tipo | Nome | Preventiva? |
|---|---|---|
| CPG | Corretiva programada | Não |
| MPV | Manutenção preventiva | Sim |
| EM | Emergencial | Não |
| INSP | Inspeção | Sim |
| MPR | Manutenção preditiva | Sim |
| MO | Melhoria operacional | Não |
| SR | Serviço | Não |
| IL | Iluminação | Sim |

Fora da lista, mas com OS na homologação: `CO` (951/ano), `MS` (11193), `MP` (317).

## 6. Sites e acessos

Sites `FABRICA` (Fábrica) e `MINERACAO` (Mineração), org `ITAMBE`. 1 gerente, com
usuário próprio no Maximo, nos 2 sites. Chaves criadas pelo ADMIN; **cliente não
quer expiração**; a empresa avisa saída de gerente.

## 7. Indicadores (como o cliente calcula)

- **Backlog:** soma de HH das OS pendentes / (HH disponíveis × FP 0,80). Em horas,
  não em quantidade de OS.
- **OS atrasadas:** status AGINSP, AGEXEC ou EMAND e início previsto < hoje (sem
  tolerância aqui; seção 4 diz 7 dias).
- **Cumprimento de preventivas:** tipos MPV, MPR, INSP, IL, **MS**; texto do guia:
  "OS nos status AGINSP, AGEXEC, EMAND / OS nos status CONCL, FECHAR", por equipe
  (Elétrica, Instrumentação, Oficina...).
- MTTR e MTBF: **não usam**.
- Reincidência: sem classe de falha; investigam pela descrição dos executantes.
- Custo: vem do Protheus pela interface, apropriado à posição ou ativo.
- Horas apontadas por equipe: por mão de obra ligada a cada equipe.

## 8. Campos customizados e relatórios

- `MODALIDADE` na OS e na preventiva (PM): tipo de manutenção, base dos indicadores
  por modalidade (nome exato do atributo a conferir no `apischema`).
- `CCI_ANOMALIA`: pendência/anomalia na OS, gera OS relacionada.
- Relatórios de referência: Mapa de Preventivas (BI; perguntas 1-3), Acompanhamento
  de Execução de OS (BI; 4-8), Itambé – Especificação de Equipamento (Maximo; 9),
  Relatório de Ocorrências Diárias (Maximo; 11-12), Acompanhamento de SS (BI; 13-14),
  Equipamentos em Manutenção Externa (BI; 15-17). Exemplos ainda não enviados.

## Conflitos e dúvidas (levar ao consultor)

1. Backlog: CONCL, FECHAR e OSFILENC marcados "conta no backlog = Sim"; APROG (maior
   grupo aberto) "Não". Coluna entendida de outro jeito?
2. Atraso: tolerância 7 dias (seção 4) × "início previsto < hoje" (seção 7).
3. "Início Previsto" = `targstartdate` ou `schedstart`?
4. Cumprimento de preventivas: fórmula escrita como pendentes/concluídas; esperado
   concluídas/(concluídas + pendentes)? Período (mês de quê)?
5. Tipos `CO`, `MS`, `MP` fora da tabela; `MS` entra no cumprimento. `CPG` é
   corretiva para reincidência?
6. Modalidade (campo) × tipo de trabalho: qual vale para a pergunta 8?
7. Backlog em HH: de onde vêm as HH previstas (`estdur`, mão de obra planejada) e as
   HH disponíveis por equipe?
8. "Setor" (pergunta 4) e "colaborador designado" (pergunta 6): quais campos?
9. Módulo de SS e manutenção externa: app SR padrão ou customizado? Onde ficam
   fornecedor e data de envio?
10. Chave sem expiração: aceitar ou recomendar rotação (segurança)?
