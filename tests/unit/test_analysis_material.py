import datetime
import json

from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.material import format_material_text, material_report

D = datetime.date
CONFIG = load_client_config("itambe")
FROM, TO = D(2026, 1, 1), D(2026, 2, 28)
_ids = iter(range(1, 1000))


def tx(refwo, itemnum, quantity, linecost, when, assetnum=None, storeloc="FAB", **extra):
    descriptions = {"I1": "ROLAMENTO", "I2": "GRAXA", "I3": "MOTOR"}
    record = {
        "refwo": refwo,
        "siteid": "FABRICA",
        "matusetransid": next(_ids),
        "actualdate": f"{when}T08:00:00",
        "itemnum": itemnum,
        "description": descriptions[itemnum],
        "quantity": quantity,
        "issueunit": "KG" if itemnum == "I2" else "PC",
        "linecost": linecost,
        "storeloc": storeloc,
        "assetnum": assetnum,
        "location": None,
    }
    record.update(extra)
    return record


TRANSACTIONS = [
    tx("100", "I1", -2, 200.0, "2026-01-05", "A1"),
    tx("100", "I1", 1, -100.0, "2026-01-06", "A1"),  # devolução
    tx("100", "I2", -5, 50.0, "2026-01-10", storeloc="28"),  # ativo e location da OS
    tx("200", "I3", -1, 1000.0, "2026-02-01"),
    tx(None, "I2", -10, 100.0, "2026-02-02"),  # sem OS
    tx("300", "I1", -1, 100.0, "2026-02-03", "A1"),  # OS não encontrada (tarefa)
]
WORK_ORDERS = [
    {
        "wonum": "100",
        "siteid": "FABRICA",
        "description": "Troca rolamento",
        "worktype": "CO",
        "assetnum": "A1",
        "location": "L1",
    },
    {
        "wonum": "200",
        "siteid": "FABRICA",
        "description": "Troca motor",
        "worktype": "MPV",
        "assetnum": "A2",
        "location": "L2",
    },
]


def test_material_report_totals():
    report = material_report(TRANSACTIONS, WORK_ORDERS, CONFIG, FROM, TO)
    assert report["transactions"] == 6
    assert (report["issues"], report["returns"]) == (5, 1)
    assert report["issued_cost"] == 1450.0
    assert report["returned_cost"] == 100.0
    assert report["net_cost"] == 1350.0
    assert report["items"] == 3
    assert report["work_orders"] == 3
    assert report["work_orders_not_found"] == 1
    assert report["without_work_order"] == {"transactions": 1, "net_cost": 100.0}
    assert report["without_asset"] == {"transactions": 1, "net_cost": 100.0}
    assert report["by_month"] == {
        "2026-01": {"net_cost": 150.0, "transactions": 3},
        "2026-02": {"net_cost": 1200.0, "transactions": 3},
    }
    assert report["by_storeroom"] == {"FAB": 1300.0, "28": 50.0}
    assert list(report["by_worktype"])[0] == "MPV"
    assert report["by_worktype"] == {
        "MPV": {"net_cost": 1000.0, "share": 74.1, "transactions": 1, "work_orders": 1},
        "CO": {"net_cost": 150.0, "share": 11.1, "transactions": 3, "work_orders": 1},
        "(sem OS)": {"net_cost": 100.0, "share": 7.4, "transactions": 1, "work_orders": 0},
        "(OS não encontrada)": {
            "net_cost": 100.0,
            "share": 7.4,
            "transactions": 1,
            "work_orders": 1,
        },
    }
    json.dumps(report)


def test_items_and_pareto():
    report = material_report(TRANSACTIONS, WORK_ORDERS, CONFIG, FROM, TO)
    assert [row["itemnum"] for row in report["by_item"]] == ["I3", "I1", "I2"]
    assert report["by_item"][1] == {
        "itemnum": "I1",
        "description": "ROLAMENTO",
        "unit": "PC",
        "net_quantity": 2.0,  # 2 - 1 devolvido + 1
        "net_cost": 200.0,
        "share": 14.8,
        "issues": 2,
        "returns": 1,
        "work_orders": 2,
        "assets": 1,
    }
    assert report["by_item"][2]["work_orders"] == 1  # a baixa sem OS não conta OS
    # 1000 / 1350 = 74% < 80%: precisa do 2º item.
    assert report["pareto"] == {"items_with_cost": 3, "items_for_80pct": 2}


def test_assets_locations_and_work_orders():
    report = material_report(TRANSACTIONS, WORK_ORDERS, CONFIG, FROM, TO)
    assets = report["by_asset"]
    assert (assets["objects"], assets["net_cost"]) == (2, 1250.0)
    assert assets["top"][0]["assetnum"] == "A2"  # pela OS 200
    a1 = assets["top"][1]
    assert a1 == {
        "assetnum": "A1",
        "siteid": "FABRICA",
        "net_cost": 250.0,
        "share": 18.5,
        "transactions": 4,
        "work_orders": 2,
        "items": 2,
        "top_item": "I1",
        "top_item_description": "ROLAMENTO",
    }
    locations = report["by_location"]
    assert [(r["location"], r["net_cost"]) for r in locations["top"]] == [
        ("L2", 1000.0),
        ("L1", 150.0),
    ]
    orders = report["by_work_order"]
    assert [(r["wonum"], r["net_cost"], r["worktype"]) for r in orders] == [
        ("200", 1000.0, "MPV"),
        ("100", 150.0, "CO"),
        ("300", 100.0, "(OS não encontrada)"),
    ]
    assert orders[0]["description"] == "Troca motor"
    assert orders[2]["description"] is None


def test_top_empty_and_text():
    report = material_report(TRANSACTIONS, WORK_ORDERS, CONFIG, FROM, TO, top=1)
    assert len(report["by_item"]) == 1
    assert len(report["by_asset"]["top"]) == 1
    assert len(report["by_work_order"]) == 1

    empty = material_report([], [], CONFIG, FROM, TO)
    assert empty["net_cost"] == 0.0
    assert empty["by_item"] == []
    assert empty["pareto"] == {"items_with_cost": 0, "items_for_80pct": 0}
    assert empty["by_month"]["2026-01"] == {"net_cost": 0.0, "transactions": 0}
    json.dumps(empty)
    format_material_text(empty)

    text = format_material_text(material_report(TRANSACTIONS, WORK_ORDERS, CONFIG, FROM, TO))
    assert "Custo líquido: 1.350,00 (baixas 1.450,00, devoluções 100,00)" in text
    assert "Pareto: 2 de 3 itens" in text
    assert "Troca motor" in text
