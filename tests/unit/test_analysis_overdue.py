import asyncio
import datetime
import json

import pytest

from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.fetch import WORK_ORDER_TOOL, fetch_overdue_candidates
from maximo_agents.analysis.overdue import days_late_bucket, format_overdue_text, overdue_report

D = datetime.date
AS_OF = D(2026, 11, 18)
CONFIG = load_client_config("itambe")


def wo(wonum, status, due, **extra):
    record = {
        "wonum": wonum,
        "siteid": "FABRICA",
        "description": f"OS {wonum}",
        "status": status,
        "worktype": "CO",
        "wopriority": 2,
        "assetnum": None,
        "location": None,
        "reportdate": "2026-01-01T08:00:00",
        "crewid": None,
        "targstartdate": due,
    }
    record.update(extra)
    return record


def test_itambe_rule():
    assert CONFIG.overdue_status_list() == ["AGEXEC", "AGINSP", "EMAND"]
    assert CONFIG.overdue_date_field == "targstartdate"
    assert CONFIG.overdue_tolerance_days == 7


@pytest.mark.parametrize(
    "days, label",
    [
        (1, "1-7"),
        (7, "1-7"),
        (8, "8-30"),
        (30, "8-30"),
        (31, "31-90"),
        (365, "91-365"),
        (366, ">365"),
    ],
)
def test_days_late_bucket(days, label):
    assert days_late_bucket(days) == label


def test_days_late_bucket_rejects_not_late():
    with pytest.raises(ValueError):
        days_late_bucket(0)


def test_overdue_report():
    records = [
        # Hoje e amanhã: no prazo (atraso é data antes de hoje).
        wo("1", "AGEXEC", "2026-11-18T10:00:00"),
        wo("2", "EMAND", "2026-11-19T00:00:00"),
        # Sem data: não conta.
        wo("3", "AGEXEC", None),
        # 1 dia: atrasada, dentro da tolerância (7).
        wo("4", "AGEXEC", "2026-11-17T23:59:00", crewid="ELETRICA", assetnum="MOI0001"),
        # 7 dias: ainda dentro da tolerância.
        wo("5", "AGINSP", "2026-11-11T08:00:00", crewid="ELETRICA", assetnum="MOI0001"),
        # 8 dias: além da tolerância.
        wo("6", "EMAND", "2026-11-10T08:00:00", crewid="MECANICA", wopriority=1),
        # 400 dias.
        wo("7", "AGEXEC", "2025-10-14T08:00:00", crewid="ELETRICA", location="L1"),
    ]
    report = overdue_report(records, CONFIG, AS_OF)
    assert report["rule"] == {
        "statuses": ["AGEXEC", "AGINSP", "EMAND"],
        "due_date_field": "targstartdate",
        "tolerance_days": 7,
    }
    assert report["in_scope"] == 7
    assert report["without_due_date"] == 1
    assert report["not_yet_due"] == 2
    assert report["without_due_date_by_status"] == {"AGEXEC": 1}
    part = report["overdue"]
    assert part["total"] == 4
    assert part["pct_of_in_scope"] == 57.1
    assert part["beyond_tolerance"] == 2
    assert part["within_tolerance"] == 2
    assert part["median_days_late"] == 7  # 1, 7, 8, 400
    assert part["max_days_late"] == 400
    assert part["by_days_late"] == {"1-7": 2, "8-30": 1, "31-90": 0, "91-365": 0, ">365": 1}
    assert part["by_crew"] == {
        "ELETRICA": {"overdue": 3, "beyond_tolerance": 1, "max_days_late": 400},
        "MECANICA": {"overdue": 1, "beyond_tolerance": 1, "max_days_late": 8},
    }
    assert list(part["by_status"]) == ["AGEXEC", "AGINSP", "EMAND"]
    assert part["by_priority"]["2"]["overdue"] == 3
    assert part["by_priority"]["1"] == {"overdue": 1, "beyond_tolerance": 1, "max_days_late": 8}
    assert part["top_assets"]["MOI0001"]["overdue"] == 2
    assert part["top_assets"]["(empty)"]["overdue"] == 2
    assert [row["wonum"] for row in part["most_late"]] == ["7", "6", "5", "4"]
    assert part["most_late"][0]["due_date"] == "2025-10-14T08:00:00"
    assert report["ignored"] == {}
    json.dumps(report)  # serializável (vai ao LLM)
    text = format_overdue_text(report)
    assert "ATRASADAS: 4 (57.1%)" in text
    assert "ELETRICA" in text


def test_tolerance_override_and_top():
    records = [
        wo("1", "AGEXEC", "2026-11-17T08:00:00", assetnum="A1"),
        wo("2", "AGEXEC", "2026-11-10T08:00:00", assetnum="A2"),
    ]
    report = overdue_report(records, CONFIG, AS_OF, tolerance_days=0, top=1)
    assert report["rule"]["tolerance_days"] == 0
    assert report["overdue"]["beyond_tolerance"] == 2
    assert list(report["overdue"]["top_assets"]) == ["A1"]  # empate: código


def test_empty_and_other_status():
    report = overdue_report([wo("1", "APROG", "2020-01-01T00:00:00")], CONFIG, AS_OF)
    assert report["in_scope"] == 0
    assert report["overdue"]["total"] == 0
    assert report["overdue"]["pct_of_in_scope"] is None
    assert report["overdue"]["median_days_late"] is None
    assert report["overdue"]["by_days_late"][">365"] == 0
    assert report["ignored"] == {"APROG": 1}
    assert "ATRASADAS: 0" in format_overdue_text(report)


def test_fetch_overdue_candidates_asks_rule_fields():
    calls = []

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        return {"total": 1, "items": [wo("1", "AGEXEC", None)], "has_more": False}

    records = asyncio.run(fetch_overdue_candidates(call_tool, CONFIG, AS_OF))
    assert len(records) == 1  # mesma OS em todas as janelas: sem repetição
    name, arguments = calls[0]
    assert name == WORK_ORDER_TOOL
    assert arguments["status"] == "AGEXEC,AGINSP,EMAND"
    assert arguments["siteid"] == "FABRICA,MINERACAO"
    assert arguments["date_from"] == "2006-01-01"
    fields = arguments["fields"].split(",")
    assert "crewid" in fields and "targstartdate" in fields
    # Pelo reportdate, não pela previsão: OS sem previsão também vêm.
    assert all(a["date_field"] == "reportdate" for _, a in calls)
