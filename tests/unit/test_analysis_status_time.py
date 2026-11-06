import datetime
import json

from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.status_time import format_status_time_text, status_time_report

D = datetime.date
CONFIG = load_client_config("itambe")
FROM, TO = D(2026, 1, 1), D(2026, 3, 31)
_ids = iter(range(1, 1000))


def change(wonum, status, when, siteid="FABRICA", changeby="USER"):
    return {
        "wonum": wonum,
        "siteid": siteid,
        "status": status,
        "changedate": f"{when}T00:00:00",
        "changeby": changeby,
        "wostatusid": next(_ids),
    }


CHANGES = [
    # OS 1: 2 d AAPROV, 10 d AGEXEC, 10 d POSEXEC, conclui em 23/01; FECHAR depois não conta.
    change("1", "AAPROV", "2026-01-01"),
    change("1", "AGEXEC", "2026-01-03"),
    change("1", "POSEXEC", "2026-01-13"),
    change("1", "CONCL", "2026-01-23", changeby="MAXADMIN"),
    change("1", "FECHAR", "2026-02-01"),
    # OS 2: 20 d AGEXEC (OS criada já em AGEXEC). Fora de ordem na entrada.
    change("2", "CONCL", "2026-01-30"),
    change("2", "AGEXEC", "2026-01-10"),
    # OS 3 (MINERACAO): 1 d AAPROV, 10 d AGEXEC, 30 d WMATL, 2 d AGEXEC.
    change("3", "AAPROV", "2026-02-01", siteid="MINERACAO"),
    change("3", "AGEXEC", "2026-02-02", siteid="MINERACAO"),
    change("3", "WMATL", "2026-02-12", siteid="MINERACAO"),
    change("3", "AGEXEC", "2026-03-14", siteid="MINERACAO"),
    change("3", "CONCL", "2026-03-16", siteid="MINERACAO"),
    # OS 4: só a conclusão no histórico.
    change("4", "CONCL", "2026-02-05"),
    # OS 5: concluída antes do período (o FECHAR no período a trouxe).
    change("5", "AGEXEC", "2025-11-01"),
    change("5", "CONCL", "2025-12-01"),
    change("5", "FECHAR", "2026-01-15"),
    # OS 6: concluída depois do período.
    change("6", "AGEXEC", "2026-03-01"),
    change("6", "CONCL", "2026-04-05"),
    # OS 7: status fora da configuração, 1 d.
    change("7", "XYZ", "2026-03-01"),
    change("7", "CONCL", "2026-03-02"),
    # OS 8: sem conclusão.
    change("8", "AGEXEC", "2026-03-01"),
]


def test_status_time_report():
    report = status_time_report(CHANGES, CONFIG, FROM, TO, worktypes=["CO"], top=20)
    assert report["work_orders"] == 4  # 1, 2, 3 e 7
    assert report["without_history"] == 1  # 4
    assert report["completed_outside_period"] == 2  # 5 e 6
    assert report["not_completed"] == 1  # 8
    assert report["worktypes"] == ["CO"]
    # Lead times 22, 20, 43 e 1.
    assert report["lead_time_days"] == {"median": 21.0, "p90": 36.7, "mean": 21.5}
    assert report["total_days"] == 86.0  # soma dos lead times
    assert report["by_month"] == {"2026-01": 2, "2026-02": 0, "2026-03": 2}
    assert report["completion_status"] == {"CONCL": 4}
    assert report["closed_by"] == {"USER": 3, "MAXADMIN": 1}
    assert report["by_class"] == {
        "open": {"days": 75.0, "share": 87.2},
        "executed": {"days": 10.0, "share": 11.6},
        "unknown": {"days": 1.0, "share": 1.2},
    }
    assert report["unknown_statuses"] == ["XYZ"]

    by_status = {row["status"]: row for row in report["by_status"]}
    assert [row["status"] for row in report["by_status"]] == [
        "AGEXEC",
        "WMATL",
        "POSEXEC",
        "AAPROV",
        "XYZ",
    ]
    assert by_status["AGEXEC"] == {
        "status": "AGEXEC",
        "class": "open",
        "work_orders": 3,
        "intervals": 4,  # 10, 20, 10 e 2
        "total_days": 42.0,
        "share": 48.8,
        "median_days": 10.0,
        "p90_days": 17.0,
        "max_days": 20.0,
    }
    assert by_status["POSEXEC"]["class"] == "executed"

    transitions = report["transitions"]
    assert transitions[0] == {
        "from": "AGEXEC",
        "to": "CONCL",
        "count": 2,
        "median_days": 11.0,
        "total_days": 22.0,
    }
    assert (transitions[1]["from"], transitions[1]["to"], transitions[1]["count"]) == (
        "AAPROV",
        "AGEXEC",
        2,
    )
    assert all(t["to"] != "FECHAR" for t in transitions)  # depois da conclusão não conta

    slowest = report["slowest"]
    assert [row["wonum"] for row in slowest] == ["3", "1", "2", "7"]
    assert slowest[0] == {
        "wonum": "3",
        "siteid": "MINERACAO",
        "lead_time_days": 43.0,
        "completed": "2026-03-16",
        "path": "AAPROV 1.0 > AGEXEC 10.0 > WMATL 30.0 > AGEXEC 2.0 > CONCL",
    }
    json.dumps(report)


def test_top_limits_lists():
    report = status_time_report(CHANGES, CONFIG, FROM, TO, top=1)
    assert len(report["transitions"]) == 1
    assert len(report["slowest"]) == 1
    assert len(report["by_status"]) == 5  # status não é cortado


def test_empty_and_text():
    report = status_time_report([], CONFIG, FROM, TO)
    assert report["work_orders"] == 0
    assert report["lead_time_days"] == {"median": None, "p90": None, "mean": None}
    assert report["by_status"] == []
    assert report["by_month"] == {"2026-01": 0, "2026-02": 0, "2026-03": 0}
    json.dumps(report)
    format_status_time_text(report)

    text = format_status_time_text(status_time_report(CHANGES, CONFIG, FROM, TO))
    assert "OS concluídas: 4 (só com a conclusão no histórico: 1" in text
    assert "tipos: todos" in text
    assert "Status fora da configuração: XYZ" in text
    assert "AAPROV 1.0 > AGEXEC 10.0 > WMATL 30.0" in text
