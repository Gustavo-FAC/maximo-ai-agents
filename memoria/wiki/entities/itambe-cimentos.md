---
title: Itambé Cimentos
type: entity
sources: []
related: [[mas-mcp-server]], [[chave-api-por-usuario]], [[automation-scripts-como-ferramentas]]
created: 2026-10-21
updated: 2026-11-06
---

# Itambé Cimentos

Cliente piloto da plataforma. Tenant `itambe` (`TENANT_ID` no `.env`).

- Ambiente de **homologação** MAS 9.2 com [[mas-mcp-server]] ativo e validado (Fase 0).
- Conexão testada em 2026-10-21: OK.
- **Chave de teste é da MAXADMIN** (temporária, só para testes iniciais). Ver
  [[chave-api-por-usuario]] sobre o risco e a troca.
- Guia de levantamento da Fase 1 em preenchimento pelo consultor funcional. Quando
  voltar: colocar em `memoria/raw/`, fazer ingest e especificar os
  [[automation-scripts-como-ferramentas]].

## Dados (homologação, 2026-10-30)

- **Homologação é só para testes e desenvolvimento** (usuário, 2026-11-06): OS abertas
  e POSEXEC antigas são lixo do processo antigo, que não fechava as OS (POSEXEC não é
  fim de processo). Indicadores reais só em produção.

- **Sites com OS** (2026-11-06): `FABRICA` (17418 OS por `reportdate` de 2025-11-05 a
  2026-11-04) e `MINERACAO` (734). Filtrar só `FABRICA` perde 4% das OS.

- **Planos de trabalho** (2026-11-03): 2102, 2025 ativos; status gravado em
  português (sinônimo **ATIVO** de ACTIVE); `templatetype` MANUTENÇÃO; 203 planos
  sem site e sem org (nível sistema); site principal `FABRICA`, org `ITAMBE`.
  `persongroup` vazio nos planos vistos. Descrição longa em ~metade, muitas vezes
  só um código (ex.: `PS1486`, talvez procedimento de segurança: perguntar).
  **Plano ligado à location, não ao ativo** (2026-11-04): `L3T05M1` tem 8 planos;
  os 3 ativos dela (ACI0343, MCA5853, PEL0151) não têm ligação direta.
- **Não usa classe de falha** (consultor funcional): sem FAILUREREPORT útil;
  `QUERYFAILUREREPORTS` cancelado ([[ferramentas-maximo]]).
- 18337 OS com `reportdate` de 2025-11-01 a 2026-10-30; 14709 ativos.
- Tipo de trabalho: corretiva = `CO`, preventiva = `MP` (a confirmar). Nas 92 OS
  com "vazamento" no período: 56 `CO`, 2 `MP`, 34 sem tipo.
- Muitas OS vêm de checklist de inspeção (descrição "NÃO CONFORME: <pergunta>").
- Descrições em maiúsculas, em geral sem acento ("OLEO").
- Perguntas ao consultor: significado dos tipos de trabalho; por que OS sem tipo;
  como separar OS de checklist das de falha.

## Paradas de ativo (2026-11-04)

- Homologação quase não usa ASSETSTATUS: ~120 linhas no total, 4 em 2025, 0 em 2026,
  site `FABRICA`, código de parada `PCE` na maioria.
- `downtime` gravado nem sempre é a diferença entre queda e retorno (MCC2213: 08:00 →
  10:56, `downtime` 2.0). ACI1020 tem 5 pares idênticos (mesma OS 979093).
- A confirmar com o consultor: se produção registra paradas no Maximo.

## Status e tipos de OS (sondagem 2026-11-04)

18152 OS com `reportdate` de 2025-11-05 a 2026-11-04 (homologação). Status são
**próprios** (valor externo). Domínio SYNONYM da OS (tela do usuário, 2026-11-06):
21 valores; classificação **decidida** (usuário, 2026-11-06): pelo valor interno, com
exceções por cliente.

| Classe | Valor interno | Status Itambé (OS no ano) |
|---|---|---|
| aberta | WAPPR | AAPROV 202 (Aguardando Aprovação), AGENV 77 (Aguardando envio) |
| aberta | APPR | APRV 27 (Aprovado), APPR, ACONDF 1 (Aguardando cond. da fábrica) |
| aberta | ? (21º valor, fora da tela) | APROG 4153 (a programar) |
| aberta | WMATL | WMATL (Aguardando material) |
| aberta | INPRG | EMAND 1727 (Em andamento), INPRG 12, AGEXEC 7 (Aguardando execução do técnico), AGEXECFIL 14 (Aguardando execução da filha), AGINSP 30 (Aguardando inspeção), DEVPCM 16 (Devolvido ao PCM), OSFILENC 4 (OS's filhas encerradas) |
| **executada** (separada, decisão do usuário) | INPRG | POSEXEC 2557 (Pós Execução) |
| fechada | COMP | CONCL 8456 (Concluído), COMP 126 (Concluídas - Tarefa - Mobile) |
| fechada | CLOSE | FECHAR 293 (Fechado) |
| fechada | HISTEDIT | EDITHIST (Editado no Histórico) |
| cancelada | CAN | CANCEL 341 (Cancelado) |
| **cancelada** (exceção: interno CLOSE) | CLOSE | PREVCAN 109 (Preventiva cancelada) |

Worktype: `MS` 11193, sem tipo 4598, `CO` 951, `MPV` 404, `INSP` 321, `MP` 317,
`MPR` 109, `CPG` 105, `IL` 85, `EM` 33, outros < 20. Leitura pelas descrições das OS
(2026-11-06, **hipóteses, perguntar ao consultor**; usuário: siglas podem vir do
inglês):
- `MS`: preventiva de rotina (lubrificação, limpeza, verificação de nível). Quase
  sumiu: 1 OS em out/2026. Parece ter virado `MPV`; juntar os dois ao comparar meses.
- `MPV`: preventiva (lubrificação, revisão, inspeção de equipamento).
- `MP`: programada/planejada (retirada de motor, usinar bucha, trocar vedação).
- `MPR`: preditiva? (troca de rolamento).
- `CO`: corretiva (confirmado antes). `EM`: emergencial.
- `INSP`: inspeção, rotas e checklists.
- `CPG`: não conformidade de checklist? ("NÃO CONFORME: ILUMINAÇÃO").
- `IL`: sem exemplo visto.
**Pendente:** valor interno do APROG; significado dos tipos (tela de tipos de
trabalho em Organizações).

## Materiais (2026-11-04)

- **Itambé não planeja material no Maximo** (usuário, 2026-11-04): WPMATERIAL vazio,
  planejamento fica fora (Protheus). Campos próprios no WPMATERIAL (`sanum` =
  solicitação do Protheus, `justificativa`, `prioridade`, `wpm1` a `wpm6`) existem,
  mas sem uso. Material na Itambé = só consumo (`QUERYMATUSAGE`).
- Baixas (MATUSETRANS): 5241 em nov/25–nov/26 (5011 baixas, 230 devoluções); dados até
  jun/2026. Site `FABRICA`, almoxarifados `FAB`, `30`. OS 1116802 = material de limpeza
  recorrente (109 baixas). `issuetype` em PT (`EMISSÃO`, `RETORNAR`); `issueid` vazio
  nas devoluções.
