import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "querymatusage" / "QUERYMATUSAGE.py"
_spec = importlib.util.spec_from_file_location("querymatusage", SCRIPT)
qmu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qmu)

BASE = {"date_from": "2026-01-01", "date_to": "2026-01-31"}


def query(**params):
    return qmu.build_query({**BASE, **params}, "GERENTE1")


def error_code(**params):
    with pytest.raises(qmu.ParamError) as exc:
        qmu.build_query(params, "GERENTE1")
    return exc.value.code


# Day, parse_date, parse_list and the rest of the common block: tested through
# test_queryworkorders.py; test_script_common.py checks the block is identical.


def test_defaults():
    q = query()
    assert q["page"] == 1
    assert q["page_size"] == qmu.DEFAULT_PAGE_SIZE
    assert q["offset"] == 0
    assert q["fields"] == list(qmu.DEFAULT_FIELDS)
    assert q["filters"] == {}
    assert q["date_field"] == "actualdate"
    assert q["order_by"] == "actualdate, matusetransid"


def test_date_range_on_transaction_inclusive():
    q = query(date_field="TransDate")
    assert [(obj, attr, day.isoformat()) for obj, attr, day in q["binds"][:2]] == [
        ("MATUSETRANS", "TRANSDATE", "2026-01-01"),
        ("MATUSETRANS", "TRANSDATE", "2026-02-01"),
    ]
    assert q["where"].startswith("transdate >= :1 and transdate < :2")
    assert q["order_by"] == "transdate, matusetransid"
    assert error_code(**BASE, date_field="reportdate") == "invalid_date_field"


def test_issues_without_work_order_included_by_default():
    q = query(assetnum="MCA5853")
    assert "workorder" not in q["where"]
    assert len(q["binds"]) == 5  # two dates, one asset, two site authorization binds


def test_dates_required():
    assert error_code(date_to="2026-01-31") == "required"
    assert error_code(date_from="2026-01-01") == "required"
    assert error_code(itemnums="10001") == "required"
    assert error_code(worktype="CO") == "required"


def test_wonums_without_dates_go_through_top_work_order():
    q = qmu.build_query({"wonums": "1564759, 1564757", "date_to": "*"}, "GERENTE1")
    assert q["date_from"] is None and q["date_to"] is None
    assert q["filters"] == {"wonums": ["1564759", "1564757"]}
    assert q["where"].startswith(qmu.WO_WHERE % " and w.wonum in (:1, :2)")
    assert q["binds"][:2] == [
        ("WORKORDER", "WONUM", "1564759"),
        ("WORKORDER", "WONUM", "1564757"),
    ]
    assert "actualdate" not in q["where"]
    assert q["where"].count(":") == len(q["binds"])


def test_work_order_scope_goes_through_wogroup_and_tositeid():
    scope = qmu.WO_WHERE % ""
    assert "t.wonum = matusetrans.refwo and t.siteid = matusetrans.tositeid" in scope
    assert "w.wonum = t.wogroup and w.siteid = t.siteid" in scope
    assert "w.istask = 0" in scope


def test_wonums_with_dates_still_validate():
    assert query(wonums="1564759")["date_from"] == "2026-01-01"
    assert error_code(wonums="1564759", date_from="2026-01-01") == "required"
    assert error_code(wonums=" , ") == "required"


def test_range_order_limit_and_format():
    assert error_code(date_from="2026-02-01", date_to="2026-01-01") == "invalid_range"
    assert error_code(date_from="2025-01-01", date_to="2026-01-02") == "range_too_large"
    assert error_code(date_from="2026-02-30", date_to="2026-03-01") == "invalid_date"


def test_transaction_filters_bound_not_inlined():
    q = query(siteid="fabrica", itemnums="10001", storeloc="alm01", assetnum="A1", location="L1")
    assert q["filters"] == {
        "siteid": ["FABRICA"],
        "itemnums": ["10001"],
        "storeloc": ["ALM01"],
        "assetnum": ["A1"],
        "location": ["L1"],
    }
    assert (
        "siteid in (:3) and itemnum in (:4) and storeloc in (:5)"
        " and assetnum in (:6) and location in (:7)"
    ) in q["where"]
    assert "FABRICA" not in q["where"]
    assert q["binds"][2:7] == [
        ("MATUSETRANS", "SITEID", "FABRICA"),
        ("MATUSETRANS", "ITEMNUM", "10001"),
        ("MATUSETRANS", "STORELOC", "ALM01"),
        ("MATUSETRANS", "ASSETNUM", "A1"),
        ("MATUSETRANS", "LOCATION", "L1"),
    ]


def test_issue_type_is_fixed_sql():
    q = query(issuetype="Issue")
    assert q["filters"] == {"issuetype": "ISSUE"}
    assert qmu.ISSUE_TYPE_WHERE["ISSUE"] in q["where"]
    assert "maxvalue = 'ISSUE'" in q["where"]
    assert len(q["binds"]) == 4  # no bind for issuetype
    assert "maxvalue = 'RETURN'" in query(issuetype="return")["where"]
    assert error_code(**BASE, issuetype="transfer") == "invalid_issuetype"
    assert error_code(**BASE, issuetype="ISSUE' OR '1'='1") == "invalid_issuetype"


def test_work_order_filters_inside_subquery():
    q = query(worktype="CO,PRV", persongroup="mec")
    assert q["filters"] == {"worktype": ["CO", "PRV"], "persongroup": ["MEC"]}
    assert (qmu.WO_WHERE % " and w.worktype in (:3, :4) and w.persongroup in (:5)") in q["where"]
    assert q["binds"][2:5] == [
        ("WORKORDER", "WORKTYPE", "CO"),
        ("WORKORDER", "WORKTYPE", "PRV"),
        ("WORKORDER", "PERSONGROUP", "MEC"),
    ]
    assert q["where"].count(":") == len(q["binds"])


def test_bind_numbers_follow_clause_order():
    q = query(siteid="S1", itemnums="I1", issuetype="issue", wonums="1", worktype="CO")
    numbers = [int(part.split()[0].strip("(),")) for part in q["where"].split(":")[1:]]
    assert numbers == list(range(1, len(q["binds"]) + 1))


def test_injection_stays_in_binds():
    payload = "X' OR '1'='1"
    q = query(assetnum=payload, worktype=payload)
    assert payload.upper() not in q["where"]
    assert ("MATUSETRANS", "ASSETNUM", payload.upper()) in q["binds"]
    assert ("WORKORDER", "WORKTYPE", payload.upper()) in q["binds"]


def test_list_limits():
    wonums = ",".join(str(n) for n in range(qmu.MAX_WONUMS))
    assert len(query(wonums=wonums)["filters"]["wonums"]) == qmu.MAX_WONUMS
    assert error_code(**BASE, wonums=wonums + ",X") == "too_many_values"
    items = ",".join(str(n) for n in range(qmu.MAX_ITEMNUMS + 1))
    assert error_code(**BASE, itemnums=items) == "too_many_values"
    many = ",".join(f"L{n}" for n in range(qmu.MAX_LIST_VALUES + 1))
    assert error_code(**BASE, location=many) == "too_many_values"


def test_site_authorization_always_applied():
    q = query(siteid="FABRICA")
    n = len(q["binds"])
    assert q["binds"][-2:] == [("GROUPUSER", "USERID", "GERENTE1")] * 2
    assert q["where"].endswith(qmu.SITE_AUTH_WHERE % (n - 1, n))


def test_authorized_sites_become_explicit_site_filter():
    q = qmu.build_query(BASE, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert q["where"].startswith("actualdate >= :1 and actualdate < :2 and siteid in (:3, :4)")
    assert q["filters"] == {}
    n = len(q["binds"])
    assert q["where"].endswith(qmu.SITE_AUTH_WHERE % (n - 1, n))
    assert q["where"].count(":") == n


def test_permission_is_fixed_in_code():
    assert (qmu.PERMISSION_APP, qmu.PERMISSION_OPTION) == ("WOTRACK", "READ")
    assert "authapp" not in qmu.PARAM_NAMES


def test_fields():
    q = query(fields="memo, Transdate, memo")
    assert q["fields"] == ["refwo", "siteid", "matusetransid", "memo", "transdate"]
    assert error_code(**BASE, fields="refwo,it1") == "unknown_field"  # client field


def test_pagination():
    q = query(page="3", page_size="500")
    assert (q["page"], q["page_size"], q["offset"]) == (3, 500, 1000)
    assert error_code(**BASE, page_size=str(qmu.MAX_PAGE_SIZE + 1)) == "out_of_range"


def test_every_parameter_is_read():
    raw, _ = qmu.collect_params(qmu.PARAM_NAMES, {}, None, None)
    assert set(raw) == set(qmu.PARAM_NAMES)
    used = {"date_from", "date_to", "date_field", "wonums", "issuetype", "fields"}
    used |= {"page", "page_size"}
    used |= {name for name, _, _, _ in qmu.LIST_FILTERS} | set(qmu.WO_FILTERS)
    assert used == set(qmu.PARAM_NAMES)


def test_response_metadata():
    q = query(page_size="50")
    resp = qmu.build_response(q, 120, [{"refwo": "1"}])
    assert (resp["total_pages"], resp["has_more"], resp["returned"]) == (3, True, 1)
    assert (resp["date_field"], resp["date_from"], resp["date_to"]) == (
        "actualdate",
        "2026-01-01",
        "2026-01-31",
    )
    assert resp["items"] == [{"refwo": "1"}]
