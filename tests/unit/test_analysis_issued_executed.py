import asyncio
import datetime
import json

import pytest

from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.fetch import WORK_ORDER_TOOL, fetch_issued_and_finished
from maximo_agents.analysis.issued_executed import (
    format_issued_executed_text,
    issued_executed_report,
    month_end,
    month_range,
    period,
)

D = datetime.date
AS_OF = D(2026, 11, 18)
CONFIG = load_client_config("itambe")


def wo(wonum, status, reported, finished=None, crew="ELETRICA", worktype="MPV"):
    return {
        "wonum": wonum,
        "siteid": "FABRICA",
        "status": status,
        "worktype": worktype,
        "reportdate": f"{reported}T08:00:00",
        "actfinish": f"{finished}T17:00:00" if finished else None,
        "crewid": crew,
    }


def test_months():
    assert month_end(D(2026, 2, 10)) == D(2026, 2, 28)
    assert month_end(D(2024, 2, 1)) == D(2024, 2, 29)
    assert month_end(D(2026, 12, 31)) == D(2026, 12, 31)
    assert month_range(D(2026, 1, 15), 3) == [D(2025, 11, 1), D(2025, 12, 1), D(2026, 1, 1)]
    assert period(D(2026, 10, 1), 2, AS_OF) == (D(2026, 9, 1), D(2026, 10, 31))
    assert period(D(2026, 11, 1), 1, AS_OF) == (D(2026, 11, 1), AS_OF)  # mês corrente
    with pytest.raises(ValueError):
        period(D(2026, 12, 1), 1, AS_OF)
    with pytest.raises(ValueError):
        month_range(D(2026, 10, 1), 13)


def test_cohort_and_flow():
    issued = [
        wo("1", "FECHAR", "2026-10-02", "2026-10-05"),  # executada no próprio mês
        wo("2", "CONCL", "2026-10-03", "2026-11-04"),  # executada, mas no mês seguinte
        wo("3", "POSEXEC", "2026-10-04"),  # executada sem actfinish
        wo("4", "EMAND", "2026-10-05"),  # aberta
        wo("5", "PREVCAN", "2026-10-06", "2026-10-06"),  # cancelada com actfinish
        wo("6", "APROG", "2026-10-07", crew=None),  # sem equipe
    ]
    finished = [
        wo("1", "FECHAR", "2026-10-02", "2026-10-05"),
        wo("5", "PREVCAN", "2026-10-06", "2026-10-06"),
        wo("9", "FECHAR", "2026-09-20", "2026-10-10"),  # emitida antes
    ]
    report = issued_executed_report(issued, finished, CONFIG, D(2026, 10, 1), 1, AS_OF)
    (month,) = report["months"]
    assert month["month"] == "2026-10" and month["partial"] is False
    assert month["totals"] == {
        "issued": 6,
        "cancelled": 1,
        "open_now": 2,
        "executed_now": 3,
        "pct_executed_now": 60.0,
        "executed_same_month": 1,
        "pct_executed_same_month": 20.0,
        "executed_in_month": 2,
        "executed_in_month_issued_before": 1,
        "pct_executed_in_month_vs_issued": 40.0,
        "executed_now_without_finish_date": 1,
    }
    crews = month["by_crew"]
    assert list(crews) == ["ELETRICA", "(empty)"]
    assert crews["ELETRICA"]["executed_now"] == 3
    assert crews["(empty)"] == {
        "issued": 1,
        "cancelled": 0,
        "open_now": 1,
        "executed_now": 0,
        "pct_executed_now": 0.0,
        "executed_same_month": 0,
        "pct_executed_same_month": 0.0,
        "executed_in_month": 0,
        "executed_in_month_issued_before": 0,
        "pct_executed_in_month_vs_issued": 0.0,
    }
    assert "COMP" in report["rule"]["executed_statuses"]
    assert report["rule"]["cancelled_statuses"] == ["CANCEL", "PREVCAN"]
    json.dumps(report)


def test_group_with_only_finished_and_several_months():
    issued = [wo("1", "FECHAR", "2026-11-02", "2026-11-03", worktype="INSP")]
    finished = [
        wo("1", "FECHAR", "2026-11-02", "2026-11-03", worktype="INSP"),
        wo("2", "FECHAR", "2026-08-01", "2026-10-15", worktype="CPG"),
    ]
    report = issued_executed_report(
        issued, finished, CONFIG, D(2026, 11, 1), 2, AS_OF, group_by="worktype"
    )
    october, november = report["months"]
    assert october["totals"]["issued"] == 0
    assert october["totals"]["pct_executed_now"] is None
    assert october["by_worktype"]["CPG"]["executed_in_month"] == 1
    assert october["by_worktype"]["CPG"]["pct_executed_in_month_vs_issued"] is None
    assert november["partial"] is True
    assert november["by_worktype"]["INSP"]["pct_executed_same_month"] == 100.0
    text = format_issued_executed_text(report)
    assert "Tipo de trabalho" in text and "2026-11 (parcial)" in text


def test_empty_and_invalid_group():
    report = issued_executed_report([], [], CONFIG, D(2026, 10, 1), 1, AS_OF)
    assert report["months"][0]["totals"]["issued"] == 0
    assert report["months"][0]["by_crew"] == {}
    assert "Equipe (crewid)" in format_issued_executed_text(report)
    with pytest.raises(ValueError):
        issued_executed_report([], [], CONFIG, D(2026, 10, 1), 1, AS_OF, group_by="site")


def test_fetch_uses_both_date_fields():
    calls = []

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        return {"total": 0, "items": [], "has_more": False}

    asyncio.run(fetch_issued_and_finished(call_tool, CONFIG, D(2026, 10, 1), D(2026, 10, 31)))
    assert [args["date_field"] for _, args in calls] == ["reportdate", "actfinish"]
    for name, args in calls:
        assert name == WORK_ORDER_TOOL
        assert args["siteid"] == "FABRICA,MINERACAO"
        assert args["fields"].endswith(",crewid")
        assert (args["date_from"], args["date_to"]) == ("2026-10-01", "2026-10-31")
