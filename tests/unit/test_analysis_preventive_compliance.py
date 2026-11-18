import asyncio
import dataclasses
import datetime
import json

import pytest

from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.fetch import WORK_ORDER_TOOL, fetch_preventive_work_orders
from maximo_agents.analysis.preventive_compliance import (
    compliance_report,
    format_compliance_text,
)

D = datetime.date
AS_OF = D(2026, 11, 18)
CONFIG = load_client_config("itambe")


def wo(wonum, status, reported="2026-10-05", crew="ELETRICA", worktype="MPV", **extra):
    return {
        "wonum": wonum,
        "siteid": "FABRICA",
        "status": status,
        "worktype": worktype,
        "reportdate": f"{reported}T08:00:00",
        "actfinish": None,
        "crewid": crew,
        **extra,
    }


def test_itambe_rule():
    assert CONFIG.compliance_done_list() == ["CONCL", "FECHAR"]
    assert CONFIG.compliance_pending_list() == ["AGEXEC", "AGINSP", "EMAND"]


def test_compliance_by_crew():
    records = [
        wo("1", "CONCL"),
        wo("2", "FECHAR"),
        wo("3", "EMAND"),
        wo("4", "APROG"),  # fora da conta
        wo("5", "PREVCAN"),  # fora da conta
        wo("6", "AGINSP", crew="OFICINA"),
        wo("7", "CONCL", reported="2026-09-30"),  # outro mês
        wo("8", "CONCL", worktype="CO"),  # não é preventiva
    ]
    report = compliance_report(records, CONFIG, D(2026, 10, 1), 1, AS_OF)
    (month,) = report["months"]
    assert month["totals"] == {
        "done": 2,
        "pending": 2,
        "compliance_pct": 50.0,
        "excluded": 2,
        "excluded_by_status": {"APROG": 1, "PREVCAN": 1},
    }
    assert month["by_crew"] == {
        "ELETRICA": {"done": 2, "pending": 1, "compliance_pct": 66.7, "excluded": 2},
        "OFICINA": {"done": 0, "pending": 1, "compliance_pct": 0.0, "excluded": 0},
    }
    assert report["rule"]["worktypes"] == ["MPV", "MPR", "INSP", "IL", "MS"]
    assert report["rule"]["month_basis"] == "reportdate"
    json.dumps(report)
    text = format_compliance_text(report)
    assert "Fora da conta: APROG 1, PREVCAN 1" in text


def test_group_by_worktype_modality_and_empty_month():
    records = [
        wo("1", "CONCL", reported="2026-11-02", worktype="INSP", modalidade="PREVENT"),
        wo("2", "EMAND", reported="2026-11-03", worktype="MS"),
    ]
    report = compliance_report(records, CONFIG, D(2026, 11, 1), 2, AS_OF, "worktype")
    october, november = report["months"]
    assert october["totals"]["compliance_pct"] is None
    assert november["partial"] is True
    assert list(november["by_worktype"]) == ["INSP", "MS"]
    by_modality = compliance_report(records, CONFIG, D(2026, 11, 1), 1, AS_OF, "modality")
    assert by_modality["months"][0]["by_modality"]["(empty)"]["pending"] == 1
    assert "Modalidade (modalidade)" in format_compliance_text(by_modality)
    with pytest.raises(ValueError):
        compliance_report(records, CONFIG, D(2026, 11, 1), 1, AS_OF, "site")
    without = dataclasses.replace(CONFIG, modality_field=None)
    with pytest.raises(ValueError):
        compliance_report(records, without, D(2026, 11, 1), 1, AS_OF, "modality")


def test_default_statuses_by_class():
    config = dataclasses.replace(
        CONFIG, compliance_done_statuses=(), compliance_pending_statuses=()
    )
    assert "POSEXEC" in config.compliance_done_list()
    assert "APROG" in config.compliance_pending_list()
    report = compliance_report([wo("1", "APROG")], config, D(2026, 10, 1), 1, AS_OF)
    assert report["months"][0]["totals"]["pending"] == 1


def test_fetch_filters_preventive_worktypes():
    calls = []

    async def call_tool(name, arguments):
        calls.append((name, arguments))
        return {"total": 0, "items": [], "has_more": False}

    asyncio.run(fetch_preventive_work_orders(call_tool, CONFIG, D(2026, 10, 1), D(2026, 10, 31)))
    ((name, args),) = calls
    assert name == WORK_ORDER_TOOL
    assert args["worktype"] == "MPV,MPR,INSP,IL,MS"
    assert args["siteid"] == "FABRICA,MINERACAO"
    assert args["date_field"] == "reportdate"
    assert args["fields"].endswith(",crewid,modalidade")
    without = dataclasses.replace(CONFIG, preventive_worktypes=())
    with pytest.raises(ValueError):
        asyncio.run(fetch_preventive_work_orders(call_tool, without, D(2026, 10, 1), AS_OF))
