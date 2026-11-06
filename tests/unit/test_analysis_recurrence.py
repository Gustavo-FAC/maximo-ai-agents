import datetime
import json

from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.recurrence import format_recurrence_text, recurrence_report

D = datetime.date
CONFIG = load_client_config("itambe")
FROM, TO = D(2026, 1, 1), D(2026, 3, 31)


def wo(wonum, reportdate, assetnum=None, location=None, status="CONCL", **extra):
    record = {
        "wonum": wonum,
        "siteid": "FABRICA",
        "description": f"Falha {wonum}",
        "status": status,
        "worktype": "CO",
        "assetnum": assetnum,
        "location": location,
        "reportdate": reportdate,
        "actfinish": None,
    }
    record.update(extra)
    return record


RECORDS = [
    # Ativo A1: 3 falhas, intervalos 10 e 40 dias -> 1 reincidência (<= 30 dias).
    wo("1", "2026-01-01T08:00:00", "A1", "L1"),
    wo("2", "2026-01-11T08:00:00", "A1", "L1"),
    wo("3", "2026-02-20T08:00:00", "A1", "L1", description="Última de A1"),
    # Ativo A2: 2 falhas no mesmo instante (checklist) -> reincidência com 0 dias.
    wo("4", "2026-03-01T10:00:00", "A2", "L1", worktype="EM"),
    wo("5", "2026-03-01T10:00:00", "A2", "L1"),
    # Mesmo código de ativo em outro site: objeto diferente.
    wo("6", "2026-01-05T08:00:00", "A1", "L9", siteid="MINERACAO"),
    # Sem ativo, só location.
    wo("7", "2026-03-10T08:00:00", None, "L2"),
    wo("8", "2026-03-20T08:00:00", "", "L2"),
    # Cancelada (PREVCAN é cancelada na Itambé): fica fora.
    wo("9", "2026-01-02T08:00:00", "A1", "L1", status="PREVCAN"),
    # Sem location e sem ativo.
    wo("10", "2026-02-01T08:00:00", None, None, status="EMAND"),
]


def test_recurrence_report():
    report = recurrence_report(RECORDS, CONFIG, FROM, TO, repeat_days=30, top=20)
    assert report["total"] == 9
    assert report["cancelled_excluded"] == 1
    assert report["without_asset"] == 3  # 7, 8 ("" conta como vazio) e 10
    assert report["without_location"] == 1
    assert report["worktypes"] == ["CO", "EM"]
    assert report["by_worktype"] == {"CO": 8, "EM": 1}
    assert report["by_status"] == {"CONCL": 8, "EMAND": 1}
    assert report["by_month"] == {"2026-01": 3, "2026-02": 2, "2026-03": 4}

    assets = report["by_asset"]
    assert assets["objects"] == 3  # A1/FABRICA, A2/FABRICA, A1/MINERACAO
    assert assets["objects_with_repeat_failures"] == 2
    assert assets["repeats"] == 2  # A1: 10 dias; A2: 0 dias
    a1 = assets["top"][0]
    assert a1 == {
        "assetnum": "A1",
        "siteid": "FABRICA",
        "failures": 3,
        "repeats": 1,
        "median_days_between": 25.0,  # 10 e 40
        "first": "2026-01-01",
        "last": "2026-02-20",
        "location": "L1",
        "last_wonum": "3",
        "last_description": "Última de A1",
    }
    a2 = assets["top"][1]
    assert (a2["assetnum"], a2["failures"], a2["repeats"], a2["median_days_between"]) == (
        "A2",
        2,
        1,
        0.0,
    )
    assert assets["top"][2]["siteid"] == "MINERACAO"
    assert assets["top"][2]["median_days_between"] is None  # 1 falha só

    locations = report["by_location"]
    assert locations["objects"] == 3  # L1, L2 (FABRICA) e L9 (MINERACAO)
    l1 = locations["top"][0]
    assert (l1["location"], l1["failures"], l1["repeats"], l1["assetnum"]) == ("L1", 5, 3, "A1")
    l2 = locations["top"][1]
    assert (l2["location"], l2["failures"], l2["repeats"], l2["assetnum"]) == ("L2", 2, 1, None)
    json.dumps(report)


def test_repeat_window_and_top():
    report = recurrence_report(RECORDS, CONFIG, FROM, TO, repeat_days=5, top=1)
    assert report["by_asset"]["repeats"] == 1  # só A2 (0 dias); A1 com 10 dias não conta
    assert len(report["by_asset"]["top"]) == 1


def test_empty_and_text():
    report = recurrence_report([], CONFIG, FROM, TO)
    assert report["total"] == 0
    assert report["by_asset"] == {
        "objects": 0,
        "objects_with_repeat_failures": 0,
        "repeats": 0,
        "top": [],
    }
    assert report["by_month"] == {"2026-01": 0, "2026-02": 0, "2026-03": 0}
    text = format_recurrence_text(recurrence_report(RECORDS, CONFIG, FROM, TO))
    assert "Corretivas: 9 (canceladas fora: 1" in text
    assert "== ATIVOS: 3 com corretiva, 2 com 2 ou mais, 2 reincidências" in text
    assert "Última de A1" in text
