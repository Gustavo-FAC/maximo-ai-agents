import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "querypms" / "QUERYPMS.py"
_spec = importlib.util.spec_from_file_location("querypms", SCRIPT)
qpm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qpm)

SITES = ["FABRICA", "MINERACAO"]


def query(**params):
    return qpm.build_query(params, "GERENTE1")


def error_code(**params):
    with pytest.raises(qpm.ParamError) as exc:
        qpm.build_query(params, "GERENTE1")
    return exc.value.code


def bind_values(q):
    return [
        value.isoformat() if isinstance(value, qpm.Day) else value for _, _, value in q["binds"]
    ]


def test_defaults_without_filters():
    # Master data: no date required, active PMs only, soonest due first.
    q = query()
    assert q["fields"] == list(qpm.DEFAULT_FIELDS)
    assert q["filters"] == {"status": ["ACTIVE"]}
    assert qpm.DEFAULT_STATUS_WHERE in q["where"]
    assert (q["due_from"], q["due_to"]) == (None, None)
    assert q["page_size"] == qpm.DEFAULT_PAGE_SIZE
    assert q["order_by"] == "nextdate, pmnum, siteid"
    assert "coalesce" not in q["where"]


def test_due_range_uses_extended_date_and_is_inclusive():
    q = query(due_from="2026-11-15", due_to="2026-11-21")
    assert q["where"].startswith(
        "coalesce(extdate, nextdate) >= :1 and coalesce(extdate, nextdate) < :2"
    )
    assert bind_values(q)[:2] == ["2026-11-15", "2026-11-22"]
    assert (q["due_from"], q["due_to"]) == ("2026-11-15", "2026-11-21")


def test_due_bounds_are_independent():
    # Only due_to: everything due up to that day (overdue PMs).
    q = query(due_to="2026-11-16")
    assert q["where"].startswith("coalesce(extdate, nextdate) < :1 and ")
    assert bind_values(q)[0] == "2026-11-17"
    q = query(due_from="2026-11-17")
    assert q["where"].startswith("coalesce(extdate, nextdate) >= :1 and ")


def test_due_errors():
    assert error_code(due_from="2026-11-21", due_to="2026-11-15") == "invalid_range"
    assert error_code(due_to="21/11/2026") == "invalid_date"
    assert error_code(due_from="2026-02-30") == "invalid_date"


def test_list_filters_and_placeholders():
    q = query(assetnum="mca6477", location="L3T05M1,l3t05m2", jpnum="JP1", crewid="ELETRICA")
    assert q["filters"]["assetnum"] == ["MCA6477"]
    assert q["filters"]["location"] == ["L3T05M1", "L3T05M2"]
    assert "assetnum in (:1)" in q["where"]
    assert "location in (:2, :3)" in q["where"]
    assert "jpnum in (:4)" in q["where"]
    assert "crewid in (:5)" in q["where"]
    assert bind_values(q)[:5] == ["MCA6477", "L3T05M1", "L3T05M2", "JP1", "ELETRICA"]


def test_pmnums_limit():
    assert query(pmnums="PM1, pm2")["filters"]["pmnums"] == ["PM1", "PM2"]
    many = ",".join(f"PM{i}" for i in range(qpm.MAX_PMNUMS + 1))
    assert error_code(pmnums=many) == "too_many_values"


def test_status():
    q = query(status="inactive")
    assert q["filters"]["status"] == ["INACTIVE"]
    assert "status in (:1)" in q["where"]
    assert qpm.DEFAULT_STATUS_WHERE not in q["where"]
    q = query(status="ALL")
    assert q["filters"]["status"] == ["ALL"]
    assert "synonymdomain" not in q["where"]
    assert error_code(status="ALL,ACTIVE") == "invalid_status"


def test_authorized_sites_explicit_when_no_siteid():
    q = qpm.build_query({}, "GERENTE1", SITES)
    assert q["where"].startswith("siteid in (:1, :2) and ")
    assert "siteid" not in q["filters"]
    q = qpm.build_query({"siteid": "fabrica"}, "GERENTE1", SITES)
    assert q["filters"]["siteid"] == ["FABRICA"]
    assert q["where"].startswith("siteid in (:1) and ")


def test_site_authorization_always_applied():
    q = query(siteid="FABRICA")
    assert q["where"].endswith(qpm.SITE_AUTH_WHERE % (len(q["binds"]) - 1, len(q["binds"])))
    assert q["binds"][-1] == ("GROUPUSER", "USERID", "GERENTE1")


def test_text_filter():
    q = query(text="lubrificacao redutor")
    assert q["filters"]["text"] == ["LUBRIFICACAO", "REDUTOR"]
    assert "upper(description) like" in q["where"]
    assert error_code(text="a") == "invalid_text"


def test_fields_and_long_description_cap():
    q = query(fields="nextdate, modalidade")
    assert q["fields"] == ["pmnum", "siteid", "nextdate", "modalidade"]
    assert error_code(fields="pmnum,password") == "unknown_field"
    q = query(fields=qpm.LONG_DESCRIPTION)
    assert q["page_size"] == qpm.MAX_DETAIL_PAGE_SIZE
    assert error_code(fields=qpm.LONG_DESCRIPTION, page_size="51") == "out_of_range"
    assert query(page_size="500")["page_size"] == 500


def test_client_fields_never_default():
    assert not set(qpm.CLIENT_FIELDS) & set(qpm.DEFAULT_FIELDS)
    assert set(qpm.CLIENT_FIELDS) <= set(qpm.FIELD_TYPES)


def test_missing_client_field():
    def absent(name):
        return False

    def present(name):
        return True

    fields = ["pmnum", "siteid", "modalidade"]
    assert qpm.missing_client_field(fields, qpm.CLIENT_FIELDS, absent) == "modalidade"
    assert qpm.missing_client_field(fields, qpm.CLIENT_FIELDS, present) is None
    # Standard fields are never checked.
    assert qpm.missing_client_field(["pmnum", "nextdate"], qpm.CLIENT_FIELDS, absent) is None


def test_response_due_date():
    q = query(due_to="2026-11-21")
    items = [
        {"pmnum": "1", "nextdate": "2026-11-20T00:00:00", "extdate": None},
        {"pmnum": "2", "nextdate": "2026-11-01T00:00:00", "extdate": "2026-11-19T00:00:00"},
        {"pmnum": "3", "nextdate": None, "extdate": None},
        {"pmnum": "4", "nextdate": "2026-11-18T00:00:00"},  # extdate not requested
    ]
    resp = qpm.build_response(q, 4, items)
    assert [item.get("due_date") for item in resp["items"]] == [
        "2026-11-20T00:00:00",
        "2026-11-19T00:00:00",
        None,
        None,
    ]
    assert "due_date" not in resp["items"][3]
    assert (resp["due_from"], resp["due_to"]) == (None, "2026-11-21")
    assert resp["filters"] == {"status": ["ACTIVE"]}
    assert resp["total"] == 4 and resp["has_more"] is False


def test_security_values_not_parameters():
    assert "authapp" not in qpm.PARAM_NAMES
    assert "authsigoption" not in qpm.PARAM_NAMES
    assert qpm.permission_binds(qpm.PERMISSION_APP, qpm.PERMISSION_OPTION, "GERENTE1")[:2] == [
        ("APPLICATIONAUTH", "APP", "PM"),
        ("APPLICATIONAUTH", "OPTIONNAME", "READ"),
    ]
