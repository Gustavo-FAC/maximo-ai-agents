import asyncio
import datetime
import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from maximo_agents.agents.recipes import HANDOFF_TOOL, WORK_ORDER_ANALYSIS
from maximo_agents.analysis.config import load_client_config
from maximo_agents.evals.__main__ import main, select
from maximo_agents.evals.cases import (
    DEFAULT_CASES,
    CaseError,
    ExpectedCall,
    load_cases,
    parse_cases,
    placeholder_dates,
)
from maximo_agents.evals.checks import (
    ToolCall,
    Transcript,
    answer_numbers,
    call_matches,
    check_case,
    ungrounded_numbers,
)
from maximo_agents.evals.runner import report, run_case, write_report

CONFIG = load_client_config("itambe")
TODAY = datetime.date(2026, 11, 18)  # quarta-feira
WO = "script_queryworkorders"


def cases_from(text: str):
    return parse_cases(text, TODAY, "sunday")


def one_case(expect: str = "", agent: str = "analise-os", question: str = "Pergunta?"):
    text = f'[[cases]]\nid = "c1"\nagent = "{agent}"\nquestion = "{question}"\n'
    if expect:
        text += "[cases.expect]\n" + expect
    return cases_from(text)[0]


# --- Arquivo de casos ---------------------------------------------------------------


def test_real_cases_file_is_valid():
    cases = load_cases(DEFAULT_CASES, TODAY, CONFIG.week_start)
    assert len(cases) >= 30
    assert len({c.id for c in cases}) == len(cases)
    by_id = {c.id: c for c in cases}
    # Semana do cliente começa no domingo.
    assert by_id["g01-mps-semana"].expect.calls[0].args == {
        "due_from": "2026-11-15",
        "due_to": "2026-11-21",
    }
    assert by_id["g12-vezes-falha"].expect.calls[0].args["date_from"] == "2026-01-01"
    # Regras gerais (defaults) valem para todos os casos.
    assert all(any("analyze_" in p for p in c.expect.answer_none) for c in cases)
    assert by_id["p38-prompt-injection"].expect.no_tools
    assert by_id["r02-conceito-mtbf"].expect.specialist == "none"


def test_placeholder_dates_monday_week():
    dates = placeholder_dates(TODAY, "monday")
    assert (dates["week_start"], dates["week_end"]) == ("2026-11-16", "2026-11-22")
    assert dates["month_start"] == "2026-11-01"
    assert dates["yesterday"] == "2026-11-17"


@pytest.mark.parametrize(
    ("expect", "message"),
    [
        ('calls = [{ tool = "changestatus" }]\n', "not available"),
        (f'calls = [{{ tool = "{WO}", args = {{ wonum = "1" }} }}]\n', "unknown args"),
        (
            'calls = [{ tool = "analyze_reliability", args = { date_to = "{amanha}" } }]\n',
            "placeholder",
        ),
        ('specialist = "analise-os"\n', "only applies"),
        (f'no_tools = true\ncalls = [{{ tool = "{WO}" }}]\n', "contradicts"),
        ("answer_any = ['(abc']\n", "bad regex"),
        ("whatever = 1\n", "unknown expect keys"),
    ],
)
def test_invalid_cases_are_rejected(expect, message):
    with pytest.raises(CaseError, match=message):
        one_case(expect)


def test_duplicated_ids_and_unknown_agent():
    case = '[[cases]]\nid = "x"\nquestion = "q"\n'
    with pytest.raises(CaseError, match="Duplicated"):
        cases_from(case + case)
    with pytest.raises(CaseError, match="unknown agent"):
        cases_from('[[cases]]\nid = "x"\nagent = "outro"\nquestion = "q"\n')


def test_router_cases_accept_specialist_tools():
    case = one_case(
        'specialist = "analise-os"\ncalls = [{ tool = "analyze_work_order_backlog" }]\n',
        agent="assistente-geral",
    )
    assert case.expect.specialist == "analise-os"


# --- Números ------------------------------------------------------------------------


def test_answer_numbers_skip_dates_times_and_codes():
    text = "Em 17/11/2026 às 08:30 (2026-11-17) o MOI0001 e a OS 1633892 tinham 7.045 abertas."
    assert [token for token, _ in answer_numbers(text)] == ["1633892", "7.045"]


def transcript(answer, result=None, question="Pergunta?"):
    calls = [ToolCall("analyze_work_order_backlog", {}, result)] if result else []
    return Transcript(question=question, answer=answer, calls=calls)


@pytest.mark.parametrize(
    ("answer", "result"),
    [
        ("São 7.045 OS abertas.", {"open": {"total": 7045}}),  # milhar pt-BR
        ("Mediana de 31,0 dias.", {"median": 31.0}),
        ("Mediana de 30,6 dias, cerca de 31 dias.", {"median": 30.62}),  # arredondado
        ("Representa 12,3% do custo.", {"share": 0.1234}),  # fração x100
        ("Representa 36,5% do custo.", {"share_pct": 36.48}),
        ("Custo de R$ 1.234,56.", {"cost": 1234.561}),
        ("Lead time de 12.5 dias.", {"lead": 12.46}),  # ponto decimal em inglês
        ("Total 2.348.", {"by_crew": [{"crew": "ELETRICA", "count": 2348}]}),
        ("O wonum é 1633892.", {"items": [{"wonum": "1633892"}]}),  # número em texto
        ("Top 5 e 3 status.", None),  # inteiros pequenos não contam
    ],
)
def test_grounded_numbers(answer, result):
    assert ungrounded_numbers(transcript(answer, result)) == []


def test_numbers_from_question_and_extra_sources():
    t = transcript("Nos últimos 90 dias, 37 OS.", {"total": 37}, question="últimos 90 dias?")
    assert ungrounded_numbers(t) == []
    t = Transcript(question="Pergunta?", answer="Hoje: 18 de novembro de 2026.")
    assert ungrounded_numbers(t) == ["18", "2026"]
    assert ungrounded_numbers(t, extra=("2026-11-18",)) == []


def test_ungrounded_numbers_are_reported():
    t = transcript(
        "São 150 OS abertas, 21,7% do total, média de 45,2 dias.",
        {"total": 149, "share": 0.2, "median": 45.0},
    )
    assert ungrounded_numbers(t) == ["150", "21,7", "45,2"]


# --- Chamadas -----------------------------------------------------------------------


def test_call_matches_defaults_case_lists_and_wildcard():
    material = ToolCall("analyze_material_usage", {})
    assert call_matches(material, ExpectedCall(("analyze_material_usage",), {"days": "365"}))
    assert not call_matches(material, ExpectedCall(("analyze_material_usage",), {"days": "90"}))

    wo = ToolCall(WO, {"assetnum": "moi0001", "worktype": "EM, CO", "text": "Rolamento"})
    assert call_matches(wo, ExpectedCall((WO,), {"assetnum": "MOI0001", "text": "rolamento"}))
    assert call_matches(wo, ExpectedCall((WO,), {"worktype": "CO,EM"}))
    assert call_matches(wo, ExpectedCall(("script_querypms", WO), {"text": "*"}))
    assert not call_matches(wo, ExpectedCall((WO,), {"location": "*"}))  # ausente, sem padrão
    assert not call_matches(wo, ExpectedCall(("script_querypms",), {}))


def failed(results):
    return {r.name for r in results if not r.ok}


def test_check_case_all_rules():
    case = one_case(
        f'calls = [{{ tool = "{WO}", args = {{ assetnum = "MOI0001" }} }}]\n'
        'forbidden_args = [{ tool = "script_querypms", args = { status = "ACTIVE" } }]\n'
        'forbidden_tools = ["script_querymatusage"]\n'
        "answer_all = ['(?i)corretiv']\n"
        "answer_any = ['(?i)somente leitura', '(?i)só leitura']\n"
        "answer_none = ['(?i)cancelei']\n"
    )
    good = Transcript(
        question="Pergunta?",
        answer="Foram 14 OS corretivas; o agente é só leitura.",
        calls=[ToolCall(WO, {"assetnum": "MOI0001"}, {"total": 14})],
    )
    assert failed(check_case(case, good)) == set()

    bad = Transcript(
        question="Pergunta?",
        answer="Cancelei 20 OS.",
        calls=[
            ToolCall("script_querypms", {"status": "active"}, {"total": 0}),
            ToolCall("script_querymatusage", {}, {"total": 1}),
        ],
    )
    assert failed(check_case(case, bad)) == {
        f"call {WO}(assetnum=MOI0001)",
        "not script_querypms(status=ACTIVE)",
        "forbidden_tools",
        "answer has /(?i)corretiv/",
        "answer has one of answer_any",
        "answer lacks /(?i)cancelei/",
        "grounded_numbers",
    }


def test_check_case_no_tools_specialist_and_errors():
    case = one_case('specialist = "none"\nno_tools = true\n', agent="assistente-geral")
    routed = Transcript(
        question="q", answer="ok", calls=[ToolCall(WO, {})], specialist="analise-os"
    )
    assert failed(check_case(case, routed)) == {"specialist", "no_tools"}
    broken = Transcript(question="q", error="TimeoutError: boom")
    results = {r.name: r for r in check_case(case, broken)}
    assert not results["completed"].ok
    assert results["completed"].detail == "TimeoutError: boom"


# --- Runner (modelo falso) ----------------------------------------------------------


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def scripted(*messages):
    return ScriptedModel(messages=iter(messages))


def tool_call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def request(*calls):
    return AIMessage(content="", tool_calls=list(calls))


class FakeMaximo:
    def __init__(self):
        self.calls = []

    async def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        return {"total": 14, "items": [{"wonum": "1633892"}], "has_more": False}


def run(coro):
    return asyncio.run(coro)


def test_run_case_agent_records_calls_and_answer():
    case = one_case(f'calls = [{{ tool = "{WO}", args = {{ assetnum = "MOI0001" }} }}]\n')
    model = scripted(
        request(tool_call(WO, {"assetnum": "MOI0001", "date_from": "2026-01-01"}, "c1")),
        request(tool_call("changestatus", {"wonum": "1"}, "c2")),
        AIMessage(content="Foram 14 OS; a mais recente é a 1633892."),
    )
    maximo = FakeMaximo()
    result = run(run_case(case, model, maximo, CONFIG, TODAY))

    assert result.passed, result.failures
    calls = result.transcript.calls
    assert [c.name for c in calls] == [WO, "changestatus"]
    assert calls[0].result["total"] == 14
    assert calls[1].failed  # erro da Toolbox também fica gravado
    assert len(maximo.calls) == 1
    assert result.transcript.specialist is None


def test_run_case_router_records_specialist_and_subgraph_calls():
    case = one_case(
        f'specialist = "analise-os"\ncalls = [{{ tool = "{WO}" }}]\n',
        agent="assistente-geral",
    )
    router = scripted(request(tool_call(HANDOFF_TOOL, {"agent": WORK_ORDER_ANALYSIS.name}, "h")))
    specialist = scripted(
        request(tool_call(WO, {"wonums": "1633892"}, "c1")),
        AIMessage(content="A OS 1633892 está aberta."),
    )
    result = run(run_case(case, specialist, FakeMaximo(), CONFIG, TODAY, router_model=router))

    assert result.passed, result.failures
    assert result.transcript.specialist == WORK_ORDER_ANALYSIS.name
    assert [c.name for c in result.transcript.calls] == [WO]
    assert result.transcript.answer == "A OS 1633892 está aberta."


def test_run_case_router_direct_answer():
    case = one_case('specialist = "none"\nno_tools = true\n', agent="assistente-geral")
    router = scripted(AIMessage(content="MTBF é o tempo médio entre falhas."))
    result = run(run_case(case, router, FakeMaximo(), CONFIG, TODAY, router_model=router))
    assert result.passed, result.failures
    assert result.transcript.specialist is None


def test_run_case_survives_model_failure():
    class Broken(ScriptedModel):
        def _generate(self, *args, **kwargs):
            raise TimeoutError("sem resposta")

    result = run(run_case(one_case(), Broken(messages=iter([])), FakeMaximo(), CONFIG, TODAY))
    assert not result.passed
    assert result.transcript.error == "TimeoutError: sem resposta"


def test_report_and_file(tmp_path):
    model = scripted(request(tool_call(WO, {"wonums": "1"}, "c1")), AIMessage(content="Foram 14."))
    result = run(run_case(one_case(), model, FakeMaximo(), CONFIG, TODAY))
    data = report([result], TODAY, "fake/model")
    assert (data["passed"], data["total"]) == (1, 1)
    assert data["cases"][0]["calls"] == [{"name": WO, "args": {"wonums": "1"}, "total": 14}]
    path = write_report(data, tmp_path / "reports")
    assert json.loads(path.read_text(encoding="utf-8"))["model"] == "fake/model"


# --- CLI ----------------------------------------------------------------------------


def test_select_and_list(capsys):
    cases = load_cases(DEFAULT_CASES, TODAY, CONFIG.week_start)
    assert [c.id for c in select(cases, "p33-backlog, g01-mps-semana", None)] == [
        "p33-backlog",
        "g01-mps-semana",
    ]
    assert {c.agent for c in select(cases, "", "assistente-geral")} == {"assistente-geral"}
    with pytest.raises(CaseError, match="Unknown case ids"):
        select(cases, "nao-existe", None)

    assert main(["--list", "--today", "2026-11-18", "--only", "g15-manutencao-externa"]) == 0
    out = capsys.readouterr().out
    assert "g15-manutencao-externa" in out
    assert "[falta: manutenção externa: fornecedor na ordem de compra" in out
    assert main(["--list", "--only", "nao-existe"]) == 2
