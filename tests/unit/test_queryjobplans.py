import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "queryjobplans" / "QUERYJOBPLANS.py"
_spec = importlib.util.spec_from_file_location("queryjobplans", SCRIPT)
qjp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qjp)

USER_BINDS = [("GROUPUSER", "USERID", "GERENTE1")] * 4


def query(**params):
    return qjp.build_query(params, "GERENTE1")


def error_code(**params):
    with pytest.raises(qjp.ParamError) as exc:
        qjp.build_query(params, "GERENTE1")
    return exc.value.code


def site_auth(first):
    auth = [qjp.SITE_AUTH_WHERE % (n, n + 1) for n in (first, first + 2)]
    return qjp.JOBPLAN_SITE_AUTH_WHERE % tuple(auth)


def test_defaults_active_status_and_site_auth():
    q = query()
    assert (q["page"], q["page_size"], q["offset"]) == (1, qjp.DEFAULT_PAGE_SIZE, 0)
    assert q["fields"] == list(qjp.DEFAULT_FIELDS)
    assert q["include_tasks"] is False
    assert q["filters"] == {"status": ["ACTIVE"]}
    assert q["order_by"] == "jpnum, pluscrevnum, siteid"
    assert q["where"] == qjp.DEFAULT_STATUS_WHERE + " and " + site_auth(1)
    assert q["binds"] == USER_BINDS


def test_default_status_by_internal_value():
    # Synonyms of ACTIVE configured by the client are matched too.
    assert "domainid = 'JOBPLANSTATUS'" in qjp.DEFAULT_STATUS_WHERE
    assert "maxvalue = 'ACTIVE'" in qjp.DEFAULT_STATUS_WHERE


def test_status_all_and_explicit():
    q = query(status="all")
    assert q["filters"] == {"status": ["ALL"]}
    assert q["where"] == site_auth(1)
    q = query(status="draft, inactive")
    assert q["filters"]["status"] == ["DRAFT", "INACTIVE"]
    assert q["where"].startswith("status in (:1, :2) and ")
    assert error_code(status="ALL,ACTIVE") == "invalid_status"


def test_siteid_keeps_plans_without_site():
    q = query(siteid="itb, ITB,mg1")
    assert q["filters"]["siteid"] == ["ITB", "MG1"]
    assert q["where"].startswith(qjp.SITE_FILTER_WHERE % ":1, :2")
    assert "siteid is null or" in qjp.SITE_FILTER_WHERE
    assert q["binds"][:2] == [("JOBPLAN", "SITEID", "ITB"), ("JOBPLAN", "SITEID", "MG1")]


def test_site_auth_covers_organization_plans():
    assert "siteid is null and (orgid is null" in qjp.JOBPLAN_SITE_AUTH_WHERE
    assert "select s.orgid from site s where" in qjp.JOBPLAN_SITE_AUTH_WHERE
    q = query(jpnums="JP1", text="motor")
    n = len(q["binds"])
    assert q["binds"][-4:] == USER_BINDS
    assert q["where"].endswith(site_auth(n - 3))
    assert q["where"].count(":") == n


def test_list_filters_bound_not_inlined():
    q = query(jpnums="jp-100, JP-200,jp-100", persongroup="mec", templatetype="maintenance")
    assert q["filters"]["jpnums"] == ["JP-100", "JP-200"]
    assert "jpnum in (:1, :2)" in q["where"]
    assert "persongroup in (:3)" in q["where"]
    assert "templatetype in (:4)" in q["where"]
    assert "JP-100" not in q["where"]
    assert ("JOBPLAN", "TEMPLATETYPE", "MAINTENANCE") in q["binds"]


def test_link_filters_use_jpassetsplink():
    q = query(assetnum="forno-1", location="moagem,FORNO", status="ALL")
    assert q["filters"]["assetnum"] == ["FORNO-1"]
    assert q["filters"]["location"] == ["MOAGEM", "FORNO"]
    assert qjp.LINK_WHERE % ("assetnum", ":1") in q["where"]
    assert qjp.LINK_WHERE % ("location", ":2, :3") in q["where"]
    assert q["binds"][:3] == [
        ("JPASSETSPLINK", "ASSETNUM", "FORNO-1"),
        ("JPASSETSPLINK", "LOCATION", "MOAGEM"),
        ("JPASSETSPLINK", "LOCATION", "FORNO"),
    ]
    assert "FORNO-1" not in q["where"]


def test_text_words_each_bound_with_wildcards():
    q = query(text="Troca  rolamento troca", status="ALL")
    assert q["filters"]["text"] == ["TROCA", "ROLAMENTO"]
    assert "upper(description) like :1 and upper(description) like :2" in q["where"]
    assert q["binds"][:2] == [
        ("JOBPLAN", "DESCRIPTION", "%TROCA%"),
        ("JOBPLAN", "DESCRIPTION", "%ROLAMENTO%"),
    ]
    assert error_code(text="100%") == "invalid_text"


def test_injection_stays_in_binds():
    payload = "X' OR '1'='1"
    q = query(assetnum=payload, jpnums=payload)
    assert payload.upper() not in q["where"]
    assert ("JPASSETSPLINK", "ASSETNUM", payload.upper()) in q["binds"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Y", True), ("yes", True), ("true", True), ("1", True), ("N", False), ("0", False)],
)
def test_include_tasks_flag(value, expected):
    assert query(include_tasks=value)["include_tasks"] is expected


def test_include_tasks_invalid():
    assert error_code(include_tasks="talvez") == "invalid_flag"


def test_include_tasks_adds_jobplanid_and_caps_page():
    q = query(include_tasks="Y")
    assert q["fields"] == list(qjp.DEFAULT_FIELDS) + ["jobplanid"]
    assert q["page_size"] == qjp.MAX_DETAIL_PAGE_SIZE
    assert error_code(include_tasks="Y", page_size="51") == "out_of_range"
    q = query(include_tasks="Y", fields="description,jobplanid")
    assert q["fields"].count("jobplanid") == 1


def test_long_description_caps_page():
    q = query(fields="description_longdescription")
    assert q["fields"] == ["jpnum", "pluscrevnum", "siteid", "description_longdescription"]
    assert q["page_size"] == qjp.MAX_DETAIL_PAGE_SIZE
    assert error_code(fields=qjp.LONG_DESCRIPTION, page_size="100") == "out_of_range"
    assert query(page_size="500")["page_size"] == 500


def test_fields():
    assert error_code(fields="jpnum,jp30") == "unknown_field"
    assert set(qjp.DEFAULT_FIELDS) <= set(qjp.FIELD_TYPES)
    assert set(qjp.KEY_FIELDS) <= set(qjp.DEFAULT_FIELDS)
    assert set(qjp.FIELD_TYPES.values()) <= {"str", "int", "float", "date", "bool"}
    assert set(qjp.TASK_FIELDS) == set(qjp.TASK_FIELD_TYPES)


def test_list_limits():
    jpnums = ",".join(f"JP{n}" for n in range(qjp.MAX_JPNUMS))
    assert len(query(jpnums=jpnums)["filters"]["jpnums"]) == qjp.MAX_JPNUMS
    assert error_code(jpnums=jpnums + ",X") == "too_many_values"
    many = ",".join(f"A{n}" for n in range(qjp.MAX_LIST_VALUES + 1))
    assert error_code(assetnum=many) == "too_many_values"


def test_permission_is_fixed_in_code():
    assert (qjp.PERMISSION_APP, qjp.PERMISSION_OPTION) == ("JOBPLAN", "READ")
    assert "authapp" not in qjp.PARAM_NAMES
    assert "authsigoption" not in qjp.PARAM_NAMES


def test_params_cover_filters():
    filter_names = {name for name, _, _, _ in qjp.LIST_FILTERS}
    filter_names |= set(qjp.LINK_FILTERS) | {"siteid", "status", "text", "include_tasks"}
    assert set(qjp.PARAM_NAMES) == filter_names | {"fields", "page", "page_size"}


def test_plan_query_reopens_page_by_jobplanid():
    pq = qjp.build_plan_query([10, 20])
    assert pq["where"] == "jobplanid in (:1, :2)"
    assert pq["binds"] == [("JOBPLAN", "JOBPLANID", 10), ("JOBPLAN", "JOBPLANID", 20)]


def test_tasks_read_through_owner_relationship():
    # JOBTASK without owner JOBPLAN fails (NullPointerException, 2026-11-03).
    assert qjp.TASK_RELATION.startswith("$")
    assert qjp.TASK_RELATION_WHERE == "jobplanid = :jobplanid"
    assert "jobplanid" not in qjp.TASK_FIELDS


def test_attach_tasks():
    items = [{"jpnum": "JP1", "jobplanid": 10}, {"jpnum": "JP2", "jobplanid": 20}]
    tasks = [{"jptask": 10, "description": "Isolar"}, {"jptask": 20, "description": "Trocar"}]
    qjp.attach_tasks(items, {10: tasks})
    assert items[0]["tasks"] == tasks
    assert items[1]["tasks"] == []


def test_response():
    q = query(page_size="50")
    resp = qjp.build_response(q, 120, [{"jpnum": "JP1"}])
    assert (resp["total_pages"], resp["has_more"], resp["returned"]) == (3, True, 1)
    assert resp["filters"] == {"status": ["ACTIVE"]}
    assert "tasks_truncated" not in resp
    q = query(include_tasks="Y")
    assert qjp.build_response(q, 1, [])["tasks_truncated"] is False
    assert qjp.build_response(q, 1, [], True)["tasks_truncated"] is True
