import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "querysrs" / "QUERYSRS.py"
_spec = importlib.util.spec_from_file_location("querysrs", SCRIPT)
qsr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qsr)

BASE = {"date_from": "2026-01-01", "date_to": "2026-01-31"}


def query(**params):
    return qsr.build_query({**BASE, **params}, "GERENTE1")


def error_code(**params):
    with pytest.raises(qsr.ParamError) as exc:
        qsr.build_query(params, "GERENTE1")
    return exc.value.code


def test_defaults():
    q = query()
    assert q["date_field"] == "reportdate"
    assert (q["page"], q["page_size"], q["offset"]) == (1, qsr.DEFAULT_PAGE_SIZE, 0)
    assert q["fields"] == list(qsr.DEFAULT_FIELDS)
    assert q["filters"] == {}
    assert q["order_by"] == "reportdate desc, ticketid"
    assert q["where"].startswith("class in (select value from synonymdomain")
    assert "maxvalue = 'SR'" in q["where"]
    assert not q["include_workorders"] and not q["include_history"]


def test_date_to_inclusive():
    q = query(date_field="statusdate")
    assert [(o, a, d.isoformat()) for o, a, d in q["binds"][:2]] == [
        ("SR", "STATUSDATE", "2026-01-01"),
        ("SR", "STATUSDATE", "2026-02-01"),
    ]
    assert "statusdate >= :1 and statusdate < :2" in q["where"]


def test_dates_required_unless_ticketids():
    assert error_code() == "required"
    assert error_code(date_from="2026-01-01") == "required"
    q = qsr.build_query({"ticketids": "1001, 1002"}, "GERENTE1")
    assert q["date_from"] is None and q["filters"]["ticketids"] == ["1001", "1002"]
    assert "ticketid in (:1, :2)" in q["where"]
    assert error_code(date_from="2025-01-01", date_to="2026-01-02") == "range_too_large"
    assert error_code(date_from="2026-02-01", date_to="2026-01-01") == "invalid_range"
    assert error_code(**BASE, date_field="wonum") == "invalid_date_field"


def test_list_filters():
    q = query(ownergroup="eletrica,MECANICA", status="NEW,QUEUED", priority="1,2")
    assert q["filters"] == {
        "status": ["NEW", "QUEUED"],
        "ownergroup": ["ELETRICA", "MECANICA"],
        "priority": [1, 2],
    }
    assert "status in (:3, :4)" in q["where"]
    assert "ownergroup in (:5, :6)" in q["where"]
    assert "reportedpriority in (:7, :8)" in q["where"]
    assert error_code(**BASE, priority="alta") == "invalid_integer"
    many = ",".join(f"G{i}" for i in range(qsr.MAX_LIST_VALUES + 1))
    assert error_code(**BASE, ownergroup=many) == "too_many_values"


def test_authorized_sites_explicit_without_siteid():
    q = qsr.build_query(BASE, "GERENTE1", ["FABRICA", "MINA"])
    assert "siteid in (:3, :4)" in q["where"]
    assert "siteid" not in q["filters"]
    q = qsr.build_query({**BASE, "siteid": "FABRICA"}, "GERENTE1", ["FABRICA", "MINA"])
    assert q["filters"]["siteid"] == ["FABRICA"]
    assert "siteid in (:3)" in q["where"]


def test_site_auth_last_and_text():
    q = query(text="vazamento bomba")
    assert q["filters"]["text"] == ["VAZAMENTO", "BOMBA"]
    assert q["binds"][-2:] == [("GROUPUSER", "USERID", "GERENTE1")] * 2
    assert "upper(description) like :3" in q["where"]


def test_detail_options_cap_page():
    for params in (
        {"include_workorders": "Y"},
        {"include_history": "yes"},
        {"fields": "description_longdescription"},
    ):
        q = query(**params)
        assert q["page_size"] == qsr.MAX_DETAIL_PAGE_SIZE
        assert error_code(**BASE, **params, page_size="51") == "out_of_range"
    q = query(include_history="Y")
    assert q["include_history"] and q["fields"][-1] == "ticketuid"
    assert query(include_workorders="N")["page_size"] == qsr.DEFAULT_PAGE_SIZE
    assert error_code(**BASE, include_history="talvez") == "invalid_flag"


def test_fields():
    q = query(fields="status,ownergroup")
    assert q["fields"] == ["ticketid", "siteid", "status", "ownergroup"]
    assert error_code(**BASE, fields="vendor") == "unknown_field"
    assert set(qsr.DEFAULT_FIELDS) <= set(qsr.FIELD_TYPES)


def test_params_cover_filters():
    names = {name for name, _, _, _ in qsr.LIST_FILTERS}
    names |= {"date_from", "date_to", "date_field", "text"}
    names |= {"include_workorders", "include_history", "fields", "page", "page_size"}
    assert set(qsr.PARAM_NAMES) == names


def test_workorder_query_has_site_auth():
    q = qsr.build_workorder_query(["1001", "1002"], "GERENTE1")
    assert "origrecordclass in (select value from synonymdomain" in q["where"]
    assert "istask = 0 and origrecordid in (:1, :2)" in q["where"]
    assert q["binds"][:2] == [("WORKORDER", "ORIGRECORDID", "1001")] + [
        ("WORKORDER", "ORIGRECORDID", "1002")
    ]
    assert q["binds"][-1] == ("GROUPUSER", "USERID", "GERENTE1")
    assert q["page_size"] == qsr.MAX_WORKORDERS and q["offset"] == 0
    assert q["fields"][0] == "origrecordid"


def test_attach_workorders_and_history():
    items = [{"ticketid": "1001", "ticketuid": 7}, {"ticketid": "1002", "ticketuid": 8}]
    rows = [
        {"origrecordid": "1001", "wonum": "W1"},
        {"origrecordid": "1001", "wonum": "W2"},
    ]
    qsr.attach_workorders(items, rows)
    assert items[0]["workorders"] == [{"wonum": "W1"}, {"wonum": "W2"}]
    assert items[1]["workorders"] == []
    qsr.attach_history(items, {8: [{"status": "NEW"}]})
    assert items[0]["history"] == [] and items[1]["history"] == [{"status": "NEW"}]


def test_sr_query_by_uid():
    q = qsr.build_sr_query([7, 8])
    assert q["where"] == "ticketuid in (:1, :2)"
    assert q["binds"] == [("SR", "TICKETUID", 7), ("SR", "TICKETUID", 8)]


def test_response_flags_only_when_requested():
    q = query()
    r = qsr.build_response(q, 0, [])
    assert "workorders_truncated" not in r and "history_truncated" not in r
    q = query(include_workorders="Y", include_history="Y")
    r = qsr.build_response(q, 1, [{"ticketid": "1"}], True, False)
    assert r["workorders_truncated"] is True and r["history_truncated"] is False
    assert r["filters"] == {} and r["total"] == 1


def test_available_fields_keeps_existing_history_fields_in_order():
    # Itambé TKSTATUS has no OWNER (BMXAA4176E, 2026-11-19).
    have = {"status", "changedate", "changeby", "ownergroup", "memo"}
    assert qsr.available_fields(qsr.HISTORY_FIELDS, lambda name: name in have) == [
        "status",
        "changedate",
        "changeby",
        "ownergroup",
        "memo",
    ]
