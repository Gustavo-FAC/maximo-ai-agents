import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "queryassets" / "QUERYASSETS.py"
_spec = importlib.util.spec_from_file_location("queryassets", SCRIPT)
qa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qa)


def query(**params):
    return qa.build_query(params, "GERENTE1")


def error_code(**params):
    with pytest.raises(qa.ParamError) as exc:
        qa.build_query(params, "GERENTE1")
    return exc.value.code


def test_defaults_need_no_filter():
    q = query()
    assert q["page"] == 1
    assert q["page_size"] == qa.DEFAULT_PAGE_SIZE
    assert q["offset"] == 0
    assert q["fields"] == list(qa.DEFAULT_FIELDS)
    assert q["filters"] == {}
    assert q["order_by"] == "siteid, assetnum"
    # Only the site authorization clause.
    assert q["where"] == qa.SITE_AUTH_WHERE % (1, 2)
    assert q["binds"] == [("GROUPUSER", "USERID", "GERENTE1")] * 2


def test_list_filters_bound_not_inlined():
    q = query(assetnums="ab-100, AB-200,ab-100", status="operating", priority="1,2")
    assert q["filters"] == {
        "assetnums": ["AB-100", "AB-200"],
        "status": ["OPERATING"],
        "priority": [1, 2],
    }
    assert "assetnum in (:1, :2)" in q["where"]
    assert "status in (:3)" in q["where"]
    assert "priority in (:4, :5)" in q["where"]
    assert "AB-100" not in q["where"]
    assert ("ASSET", "PRIORITY", 2) in q["binds"]
    assert q["where"].count(":") == len(q["binds"])


def test_every_list_filter_maps_to_asset_attribute():
    params = {name: "X" for name, _, kind, _ in qa.LIST_FILTERS if kind == "str"}
    q = qa.build_query({**params, "priority": "1"}, "GERENTE1")
    for name, attribute, _, _ in qa.LIST_FILTERS:
        assert f"{attribute} in (" in q["where"], name
    assert set(q["filters"]) == {name for name, _, _, _ in qa.LIST_FILTERS}


def test_ancestor_uses_hierarchy_subselect():
    q = query(ancestor="forno-1,moinho-2", siteid="ITB")
    assert q["filters"]["ancestor"] == ["FORNO-1", "MOINHO-2"]
    assert qa.ANCESTOR_WHERE % ":2, :3" in q["where"]
    assert "aa.assetnum <> aa.ancestor" in qa.ANCESTOR_WHERE  # descendants only
    assert q["binds"][1:3] == [
        ("ASSETANCESTOR", "ANCESTOR", "FORNO-1"),
        ("ASSETANCESTOR", "ANCESTOR", "MOINHO-2"),
    ]
    assert "FORNO-1" not in q["where"]


def test_text_words_each_bound_with_wildcards():
    q = query(text="  Motor   bomba motor ")
    assert q["filters"]["text"] == ["MOTOR", "BOMBA"]
    assert "upper(description) like :1 and upper(description) like :2" in q["where"]
    assert q["binds"][:2] == [
        ("ASSET", "DESCRIPTION", "%MOTOR%"),
        ("ASSET", "DESCRIPTION", "%BOMBA%"),
    ]
    assert "MOTOR" not in q["where"]


def test_text_accented():
    assert query(text="válvula elétrica")["filters"]["text"] == ["VÁLVULA", "ELÉTRICA"]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("a", "invalid_text"),
        ("motor x", "invalid_text"),
        ("100%", "invalid_text"),
        ("bomba_1", "invalid_text"),
        ("aa bb cc dd ee ff", "too_many_values"),
        ("m" * (qa.MAX_TEXT_LENGTH + 1), "out_of_range"),
    ],
)
def test_text_rejected(text, code):
    assert error_code(text=text) == code


def test_text_unset_ignored():
    assert query(text="*")["filters"] == {}
    assert query(text="   ")["filters"] == {}


def test_injection_stays_in_binds():
    payload = "X' OR '1'='1"
    q = query(location=payload, text="abc' or 1=1 --")
    assert payload.upper() not in q["where"]
    assert "OR 1=1" not in q["where"].upper()
    assert ("ASSET", "LOCATION", payload.upper()) in q["binds"]


def test_list_limits():
    assetnums = ",".join(str(n) for n in range(qa.MAX_ASSETNUMS))
    assert len(query(assetnums=assetnums)["filters"]["assetnums"]) == qa.MAX_ASSETNUMS
    assert error_code(assetnums=assetnums + ",X") == "too_many_values"
    many = ",".join(f"S{n}" for n in range(qa.MAX_LIST_VALUES + 1))
    assert error_code(ancestor=many) == "too_many_values"
    assert error_code(priority="1,alta") == "invalid_integer"


def test_site_authorization_always_last():
    q = query(siteid="ITB", text="motor")
    n = len(q["binds"])
    assert q["binds"][-2:] == [("GROUPUSER", "USERID", "GERENTE1")] * 2
    assert q["where"].endswith(qa.SITE_AUTH_WHERE % (n - 1, n))


def test_permission_is_fixed_in_code():
    assert (qa.PERMISSION_APP, qa.PERMISSION_OPTION) == ("ASSET", "READ")
    assert qa.permission_binds(qa.PERMISSION_APP, qa.PERMISSION_OPTION, "GERENTE1") == [
        ("APPLICATIONAUTH", "APP", "ASSET"),
        ("APPLICATIONAUTH", "OPTIONNAME", "READ"),
        ("GROUPUSER", "USERID", "GERENTE1"),
    ]
    assert "authapp" not in qa.PARAM_NAMES
    assert "authsigoption" not in qa.PARAM_NAMES


def test_fields():
    q = query(fields="Description, isrunning, description")
    assert q["fields"] == ["assetnum", "siteid", "description", "isrunning"]
    assert error_code(fields="assetnum,cci_critic") == "unknown_field"
    assert set(qa.DEFAULT_FIELDS) <= set(qa.FIELD_TYPES)
    assert set(qa.FIELD_TYPES.values()) <= {"str", "int", "float", "date", "bool"}


def test_pagination():
    q = query(page="3", page_size="50")
    assert (q["page"], q["page_size"], q["offset"]) == (3, 50, 100)
    assert error_code(page_size=str(qa.MAX_PAGE_SIZE + 1)) == "out_of_range"
    assert error_code(page="0") == "out_of_range"


def test_params_cover_filters():
    filter_names = {name for name, _, _, _ in qa.LIST_FILTERS} | {"ancestor", "text"}
    assert set(qa.PARAM_NAMES) == filter_names | {"fields", "page", "page_size"}


def test_collect_params():
    raw, sources = qa.collect_params(
        qa.PARAM_NAMES, {"text": "motor", "siteid": "*"}, {"siteid": "ITB"}, None
    )
    assert (raw["text"], raw["siteid"]) == ("motor", "ITB")
    assert sources == {"text": "variable", "siteid": "body"}
    assert set(raw) == set(qa.PARAM_NAMES)


def test_response():
    q = query(page_size="50", status="OPERATING")
    resp = qa.build_response(q, 120, [{"assetnum": "A1"}])
    assert resp["total_pages"] == 3
    assert resp["has_more"] is True
    assert resp["returned"] == 1
    assert resp["filters"] == {"status": ["OPERATING"]}
    assert qa.build_response(q, 0, [])["total_pages"] == 0
