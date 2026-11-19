---
title: Perguntas ao consultor funcional (Itambé, consolidadas)
type: synthesis
sources: [raw/guia-levantamento-fase1-itambe-2026-11-16.docx]
related: [[guia-levantamento-fase1]], [[itambe-cimentos]], [[estado-do-projeto]]
created: 2026-11-18
updated: 2026-11-18
---

# Perguntas ao consultor funcional (Itambé)

Lista única das dúvidas abertas, juntando as 10 do [[guia-levantamento-fase1]] e os
achados nos dados de homologação (até 2026-11-18). Ordem: o que bloqueia indicador
primeiro. Números = homologação; "Q" = pergunta do gerente no guia. Ao receber
resposta: registrar aqui, no [[estado-do-projeto]] e na config do cliente.

## Respostas recebidas (2026-11-18, no doc compartilhado)

Itens 1 a 14 respondidos; 15 a 22 sem resposta. "Suponha" = consultor não sabe e
pediu para decidirmos.

| # | Resposta | O que fizemos / consequência |
|---|---|---|
| 1 | Cópia de produção de ~7 meses atrás (~abr/2026) | Dados depois de abr/2026 são uso de teste; validar volumes com dados até mar/2026. |
| 2 | `targstartdate` | Confirmado no `itambe.toml`. Tolerância continua aberta (mantida 7). |
| 3 | Era o processo antigo; não precisa sair do indicador | MS em EMAND fica. Indicadores da homologação refletem o processo antigo. |
| 4 | Não sei: suponha | **Suposição:** coorte, % das emitidas no mês já executadas (`pct_executed_now`); `[issued_executed] measure` no TOML, `rule.primary_measure` no relatório. |
| 5 | No processo antigo era definido (a equipe) | OS sem equipe aparecem como `(empty)`; nada a mudar. |
| 6 | Campo `MODALIDADE` | Confirmado (`modality_field`). |
| 7 | Concluídas ÷ (concluídas + pendentes) | Fórmula do cumprimento de preventivas definida; período ainda aberto (suposição: mês de abertura). |
| 8 | Não sei: suponha | **Suposição:** OS preventivas nascem fora da PM; cumprimento pelos tipos preventivos (MPV, MPR, INSP, IL, MS), não por `pmnum`. |
| 9 | PMs ficam ativas porque o processo antigo não as fechava; processo novo entrando em produção agora | "MPs vencidas" pela PM não é confiável na homologação. |
| 10 | Sim, backlog em HH previstas e HH disponíveis | Origem das HH ainda aberta (`estdur` ou mão de obra planejada; HH disponíveis por equipe). |
| 11 | Não tem campo "setor" | Pergunta 4 sem "setor": responder por equipe, ativo ou location. |
| 12 | Mão de obra planejada | Filtro `laborcode` (WPLABOR, na OS ou em tarefa) no `QUERYWORKORDERS` (2026-11-18), falta reinstalar. |
| 13 | SR padrão (Maximo/Mobile); grupo proprietário = `ownergroup`; fornecedor na ordem de compra; cadastro em Empresas | Script `QUERYSRS` (app SR, `ownergroup`, histórico, OS geradas; 2026-11-18), falta instalar. Manutenção externa pela ordem de compra: 2º passo. |
| 14 | Alguns em CV, outros em kW, conforme a classificação | Filtro por especificação no `QUERYASSETS` converte CV, kW, HP, W, MW (e V, kV) no SQL (2026-11-18), falta reinstalar. |

## Novas (2026-11-18, depois das respostas)

23. **Cumprimento de preventivas fora da conta:** pela fórmula do guia, OS em APROG
    (aguardando programação) não entram. Em mar/2026 foram 2818 de 4605 preventivas
    (63,3% de cumprimento sobre as 1562 que entram). Está certo deixá-las fora? COMP
    (concluída pelo mobile) e POSEXEC (pós-execução) contam como concluídas?

## 0. Base de homologação

1. **De quando é a cópia de produção?** Volume cai muito de mai/2026 a ago/2026
   (202 OS em 3 meses, contra 2 a 6 mil/mês de nov/2025 a mar/2026). Os números das
   análises valem para essa base, não para produção (~3000 OS/mês pelo guia).

## A. Bloqueiam indicadores já prontos

2. **OS atrasadas (Q4): campo e tolerância.** "Início Previsto" é `targstartdate`
   (início meta, preenchido em 90% das OS nos status de atraso) ou `schedstart`
   (início programado, 42%)? Tolerância: 7 dias (seção 4 do guia) ou nenhuma (seção
   7)? Hoje mostramos as duas contagens.
3. **87,7% das OS estão atrasadas** (2049 de 2336 em AGINSP/AGEXEC/EMAND; mediana
   288 dias, máximo 1331): quase todas tipo **MS** em **EMAND**. É o processo real ou
   OS de MS que nunca são fechadas? Devem sair do indicador?
4. **Emitidas × executadas (Q7): qual cálculo o Power BI usa?**
   (a) das OS emitidas no mês, quantas já foram executadas; ou (b) OS executadas no
   mês (de qualquer mês de emissão) ÷ emitidas no mês. Outubro/2026: (a) 24,0%, (b)
   30,3%. Executada = CONCL, FECHAR, COMP, EDITHIST e POSEXEC? Canceladas (CANCEL,
   PREVCAN) ficam fora do percentual?
5. **OS sem equipe:** 126 das 546 OS emitidas em out/2026 sem `crewid`, todas abertas
   (APROG/AGENV?). A equipe é definida depois? Em que equipe contam no indicador?
6. **Modalidade (Q8):** o indicador é pelo campo `MODALIDADE` ou pelo tipo de
   trabalho? O campo vem vazio em 64% das OS de out/2026 (49% em 12 meses; quase todas
   as vazias são MS). É obrigatório em produção?
7. **Cumprimento de preventivas:** a fórmula do guia está escrita como "OS nos status
   AGINSP, AGEXEC, EMAND / OS nos status CONCL, FECHAR". O esperado seria concluídas ÷
   (concluídas + pendentes)? Período: mês de quê (abertura, vencimento, conclusão)?
8. **OS preventivas sem PM:** OS MPV e INSP recentes vêm quase todas sem `pmnum`
   (mesmo com plano de trabalho). Como nascem: rota, criação manual, app de checklist?
9. **PMs vencidas:** 4138 das 7037 PMs ativas com vencimento já passado, algumas de
   2007 a 2012 (ex.: MSFAB_20, última conclusão 2025, próximo vencimento 2012). São PMs
   abandonadas, base desatualizada ou geração fora do Maximo? Sem isso, "MPs vencidas"
   (Q1) não é confiável.
10. **Backlog:** a coluna "conta no backlog" marca CONCL, FECHAR e OSFILENC como Sim e
    APROG (maior grupo aberto) como Não. Foi entendida de outro jeito? Para backlog em
    horas: de onde vêm as HH previstas (`estdur`? mão de obra planejada?) e as HH
    disponíveis por equipe?

## B. Campos para perguntas ainda sem resposta

11. **"Setor" (Q4):** qual campo da OS?
12. **"Colaborador designado" (Q6):** `lead`, designação (ASSIGNMENT) ou mão de obra
    planejada?
13. **SS e manutenção externa (Q13-17):** app de SR padrão ou customizado? "Grupo
    proprietário" = `ownergroup`? Onde ficam fornecedor e data de envio da manutenção
    externa (a OS tem `fornecedor`)?
14. **Especificação (Q10, "motores de 50 CV"):** qual atributo de especificação e
    unidade (CV, kW)? Precisamos do nome exato para o filtro.

## C. Códigos e regras do cliente

15. **Tipos fora da tabela:** `MS` (11193 OS/ano, quase sumiu em out/2026: virou
    `MPV`?), `CO` (951) e `MP` (317). `CPG` (corretiva programada) entra como corretiva
    na reincidência? Hoje corretivas = CO e EM.
16. **OS sem tipo** (4598/ano) e OS de checklist ("NÃO CONFORME: ..."): como separar
    falha real de não conformidade de inspeção?
17. **Prioridade do checklist:** a descrição longa traz `Mel/Imp/Imi` e `Prio`.
    Inferimos: impacto + iminente = 1, impacto sem iminente = 2, sem impacto = 3,
    melhoria = 4. Confere?
18. **APROG:** qual o valor interno (WAPPR, APPR?) no domínio de status?
19. **Planos de trabalho:** o que são os códigos na descrição longa (ex.: `PS1486`)?
    O plano é ligado só à location (visto na homologação) ou também ao ativo?

## D. Baixa prioridade (indicadores que o cliente não usa hoje)

20. **MTTR:** `actstart` é preenchido na abertura? (Fica quase igual ao `reportdate`;
    OS fechadas semanas depois inflam o tempo.) O reparo deveria ser pelas horas
    apontadas?
21. **Paradas:** produção registra paradas de ativo no Maximo? Homologação quase não
    tem (0 em 2026).

## E. Segurança

22. **Chave de API sem expiração:** o cliente não quer expiração. Recomendamos
    rotação periódica (ex.: anual) e revogação na saída do gerente. Aceitam?
