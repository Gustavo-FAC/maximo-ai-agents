import datetime
import json

from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.reliability import (
    downtime_reliability,
    flag,
    format_reliability_text,
    reliability_report,
    work_order_reliability,
)

D = datetime.date
CONFIG = load_client_config("itambe")
FROM, TO = D(2026, 1, 1), D(2026, 1, 10)  # 10 dias = 240 h


def wo(wonum, reportdate, assetnum, location, actstart=None, actfinish=None, **extra):
    record = {
        "wonum": wonum,
        "siteid": "FABRICA",
        "description": f"Falha {wonum}",
        "status": "CONCL",
        "worktype": "CO",
        "assetnum": assetnum,
        "location": location,
        "reportdate": reportdate,
        "actstart": actstart,
        "actfinish": actfinish,
    }
    record.update(extra)
    return record


WORK_ORDERS = [
    # A1: 2 falhas, reparos de 2 h e 6 h.
    wo("1", "2026-01-02T08:00:00", "A1", "L1", "2026-01-02T09:00:00", "2026-01-02T11:00:00"),
    wo("2", "2026-01-05T08:00:00", "A1", "L1", "2026-01-05T08:00:00", "2026-01-05T14:00:00"),
    # A2: 1 falha sem datas de execução; 1 com fim antes do início.
    wo("3", "2026-01-03T08:00:00", "A2", "L1", worktype="EM"),
    wo("4", "2026-01-04T08:00:00", "A2", "L1", "2026-01-04T10:00:00", "2026-01-04T09:00:00"),
    # A3: 1 falha longa, 30 h de reparo (muitas horas, poucas falhas).
    wo("5", "2026-01-06T08:00:00", "A3", "L2", "2026-01-06T08:00:00", "2026-01-07T14:00:00"),
    # Sem ativo, só location.
    wo("6", "2026-01-07T08:00:00", None, "L2", "2026-01-07T08:00:00", "2026-01-07T09:00:00"),
    # Cancelada: fora.
    wo("7", "2026-01-08T08:00:00", "A1", "L1", status="PREVCAN"),
]


def test_work_order_basis_totals_and_mttr():
    report = work_order_reliability(WORK_ORDERS, CONFIG, FROM, TO)
    assert report["failures"] == 6
    assert report["cancelled_excluded"] == 1
    assert report["with_repair_time"] == 4  # 2, 6, 30 e 1 h
    assert report["without_repair_dates"] == 1
    assert report["finish_before_start"] == 1
    assert report["without_asset"] == 1
    assert report["without_location"] == 0
    assert report["mttr_hours"] == {"mean": 9.75, "median": 4.0, "p90": 22.8}
    assert report["repair_hours"] == 39.0
    assert report["by_worktype"] == {"CO": 5, "EM": 1}
    assert report["by_month"] == {"2026-01": 6}


def test_work_order_basis_per_asset():
    assets = work_order_reliability(WORK_ORDERS, CONFIG, FROM, TO)["by_asset"]
    assert assets["objects"] == 3
    a1, a2, a3 = assets["top_by_failures"]
    assert a1 == {
        "assetnum": "A1",
        "siteid": "FABRICA",
        "failures": 2,
        "mtbf_days": 5.0,  # 10 dias / 2 falhas
        "mttr_hours": 4.0,
        "median_repair_hours": 4.0,
        "repair_hours": 8.0,
        "with_repair_time": 2,
        "location": "L1",
        "last_wonum": "2",
        "last": "2026-01-05",
    }
    # A2: 2 falhas, nenhuma com tempo de reparo válido.
    assert (a2["assetnum"], a2["failures"], a2["mttr_hours"], a2["repair_hours"]) == (
        "A2",
        2,
        None,
        0.0,
    )
    assert (a3["assetnum"], a3["mtbf_days"], a3["mttr_hours"]) == ("A3", 10.0, 30.0)
    # Por horas de reparo: A3 primeiro; A2 (0 h) fica de fora.
    assert [r["assetnum"] for r in assets["top_by_repair_hours"]] == ["A3", "A1"]


def test_work_order_basis_per_location():
    locations = work_order_reliability(WORK_ORDERS, CONFIG, FROM, TO)["by_location"]
    l1, l2 = locations["top_by_failures"]
    assert (l1["location"], l1["failures"], l1["assetnum"]) == ("L1", 4, "A1")
    assert (l2["location"], l2["failures"], l2["repair_hours"], l2["mttr_hours"]) == (
        "L2",
        2,
        31.0,
        15.5,
    )


def change(assetnum, changedate, isrunning, downtime=0.0, ident=0, **extra):
    record = {
        "assetnum": assetnum,
        "siteid": "FABRICA",
        "assetstatusid": ident,
        "changedate": changedate,
        "isrunning": isrunning,
        "downtime": downtime,
        "code": None,
        "operational": False,
        "wonum": None,
        "location": "L1",
    }
    record.update(extra)
    return record


CHANGES = [
    # M1: cadastro (retorno sem queda), 2 paradas no período (2 h e 4 h, gravado 2.0 e 3.0).
    change("M1", "2009-05-01T00:00:00", True, ident=1),
    change("M1", "2026-01-02T08:00:00", False, ident=2, code="QUEBRA", wonum="100"),
    change("M1", "2026-01-02T10:00:00", True, 2.0, ident=3),
    change("M1", "2026-01-04T00:00:00", False, ident=4, code="ELET"),
    change("M1", "2026-01-04T04:00:00", True, 3.0, ident=5),
    # M2: queda antes do período, retorno no período: 12 h dentro, nenhuma parada nova.
    change("M2", "2025-12-31T12:00:00", False, ident=6),
    change("M2", "2026-01-01T12:00:00", True, 24.0, ident=7),
    # M3: par repetido (homologação) e queda no período sem retorno (parado no fim).
    change("M3", "2026-01-05T00:00:00", False, ident=8, operational=True),
    change("M3", "2026-01-05T06:00:00", True, 6.0, ident=9),
    change("M3", "2026-01-05T00:00:00", False, ident=10, operational=True),
    change("M3", "2026-01-05T06:00:00", True, 6.0, ident=11),
    change("M3", "2026-01-10T00:00:00", "0", ident=12, operational="1"),
    # M4: parada toda antes do período: fora. Data ilegível: fora.
    change("M4", "2025-06-01T00:00:00", False, ident=13),
    change("M4", "2025-06-02T00:00:00", True, 24.0, ident=14),
    change("M4", "data errada", True, ident=15),
]


def test_downtime_basis_totals():
    report = downtime_reliability(CHANGES, FROM, TO)
    assert report["stops"] == 4  # M1: 2; M3: 05/01 e 10/01
    assert report["completed_stops"] == 3
    assert report["down_at_end_of_period"] == 1
    assert report["assets_with_downtime"] == 3
    # M1 6 h + M2 12 h + M3 6 h + M3 24 h (10/01 até o fim do período).
    assert report["downtime_hours"] == 48.0
    assert report["recorded_downtime_hours"] == 11.0  # 2 + 3 + 6
    assert report["mttr_hours"] == {"mean": 4.0, "median": 4.0, "p90": 5.6}
    assert report["duplicates_removed"] == 2
    assert report["unreadable_changes"] == 1
    assert report["by_code"]["QUEBRA"] == 1 and report["by_code"]["ELET"] == 1
    assert sum(report["by_code"].values()) == 4
    assert report["by_operational"] == {"no": 2, "yes": 2}
    assert report["by_month"] == {"2026-01": 4}


def test_downtime_basis_per_asset():
    top = downtime_reliability(CHANGES, FROM, TO)["by_asset"]["top"]
    assert [r["assetnum"] for r in top] == ["M3", "M2", "M1"]  # por horas paradas
    m3, m2, m1 = top
    assert m1 == {
        "assetnum": "M1",
        "siteid": "FABRICA",
        "stops": 2,
        "downtime_hours": 6.0,
        "mttr_hours": 3.0,
        "mtbf_days": 4.9,  # (240 - 6) / 2 / 24 = 4,875
        "availability_pct": 97.5,
        "recorded_downtime_hours": 5.0,
        "down_at_end": False,
        "location": "L1",
        "last_code": "ELET",
        "last_wonum": "100",
    }
    # M2: só horas, sem parada iniciada no período: sem MTBF nem MTTR.
    assert (m2["stops"], m2["downtime_hours"], m2["mtbf_days"], m2["mttr_hours"]) == (
        0,
        12.0,
        None,
        None,
    )
    assert m2["availability_pct"] == 95.0
    assert (m3["stops"], m3["downtime_hours"], m3["mttr_hours"], m3["down_at_end"]) == (
        2,
        30.0,
        6.0,
        True,
    )
    assert m3["mtbf_days"] == 4.4  # (240 - 30) / 2 / 24 = 4,375


def test_empty_inputs():
    report = reliability_report([], [], CONFIG, FROM, TO)
    assert report["work_orders"]["failures"] == 0
    assert report["work_orders"]["mttr_hours"] == {"mean": None, "median": None, "p90": None}
    assert report["work_orders"]["by_asset"] == {
        "objects": 0,
        "top_by_failures": [],
        "top_by_repair_hours": [],
    }
    assert report["downtime"]["stops"] == 0
    assert report["downtime"]["by_asset"] == {"assets": 0, "top": []}
    json.dumps(report)  # serializável (vai ao LLM)
    assert "BASE PARADAS" in format_reliability_text(report)


def test_report_scope_and_text():
    report = reliability_report(
        WORK_ORDERS, CHANGES, CONFIG, FROM, TO, assetnums=["A1"], locations=[], top=1
    )
    assert report["period_days"] == 10
    assert report["assetnums"] == ["A1"]
    assert len(report["work_orders"]["by_asset"]["top_by_failures"]) == 1
    assert len(report["downtime"]["by_asset"]["top"]) == 1
    text = json.dumps(report, ensure_ascii=False)
    assert "NaN" not in text and "NaT" not in text
    formatted = format_reliability_text(report)
    assert "ativos A1" in formatted and "BASE OS CORRETIVAS" in formatted


def test_flag():
    values = (True, False, 1, 0, "1", "0", "Y", "n", "true")
    assert [flag(v) for v in values] == [True, False, True, False, True, False, True, False, True]
    assert flag(None) is None and flag(float("nan")) is None and flag("x") is None
