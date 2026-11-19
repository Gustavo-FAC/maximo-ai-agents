# QUERYSRS - read-only service request (SR) query, published as an MCP tool.
#
# Maximo Manage automation script without launch point, language Jython 2.7.
# Source of truth: maximo_scripts/querysrs/. Never edit directly in Maximo.
#
# Code must run on Jython 2.7 and CPython 3: the pure functions below (parsing,
# validation, where clause) are tested by tests/unit/test_querysrs.py.
# Java/Maximo imports live only inside runtime functions. No Python standard library
# imports: Maximo's Jython does not ship it ("No module named datetime").

# --- BEGIN COMMON (identical in every script; see tests/unit/test_script_common.py) ---

# Values that mean "parameter not informed" (literal variables need a default).
UNSET_VALUES = ("", "*")

# Required permission, checked in code. Not script variables: every variable becomes
# a tool parameter, so the caller could override authapp/authsigoption.
PERMISSION_WHERE = (
    "app = :1 and optionname = :2"
    " and groupname in (select groupname from groupuser where userid = :3)"
)

# Only sites the calling user is authorized for (defense in depth).
SITE_AUTH_WHERE = (
    "(exists (select 1 from groupuser gu, maxgroup mg"
    " where gu.groupname = mg.groupname and gu.userid = :%d and mg.authallsites = 1)"
    " or siteid in (select sa.siteid from siteauth sa, groupuser gu"
    " where sa.groupname = gu.groupname and gu.userid = :%d))"
)

# Implicit variables Maximo may inject; logged by name to learn which exist on the
# MCP path.
IMPLICIT_NAMES = ("request", "requestBody", "userInfo", "service", "httpMethod")

# Parameter "text": words that must all appear in the description.
MAX_TEXT_WORDS = 5
MIN_WORD_LENGTH = 2
MAX_TEXT_LENGTH = 100
TEXT_WHERE = "upper(description) like :%d"


class ParamError(Exception):
    def __init__(self, code, parameter, message):
        Exception.__init__(self, message)
        self.code = code
        self.parameter = parameter
        self.message = message


def to_text(value):
    # "%s" keeps unicode on Jython 2.7; str() fails on non-ASCII (accented values).
    return "%s" % (value,)


def is_unset(value):
    return value is None or to_text(value).strip() in UNSET_VALUES


class Day(object):
    """Calendar date as days since 1970-01-01 (Hinnant's civil calendar algorithms)."""

    def __init__(self, ordinal):
        self.ordinal = ordinal

    @classmethod
    def from_ymd(cls, year, month, day):
        y = year - 1 if month <= 2 else year
        era = y // 400
        yoe = y - era * 400
        doy = (153 * (month - 3 if month > 2 else month + 9) + 2) // 5 + day - 1
        doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
        return cls(era * 146097 + doe - 719468)

    def ymd(self):
        z = self.ordinal + 719468
        era = z // 146097
        doe = z - era * 146097
        yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
        doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
        mp = (5 * doy + 2) // 153
        day = doy - (153 * mp + 2) // 5 + 1
        month = mp + 3 if mp < 10 else mp - 9
        year = yoe + era * 400 + (1 if month <= 2 else 0)
        return (year, month, day)

    def isoformat(self):
        return "%04d-%02d-%02d" % self.ymd()


def parse_iso_day(text):
    """Day from YYYY-MM-DD, or None if text is not a valid calendar date."""
    parts = text.split("-")
    if [len(part) for part in parts] != [4, 2, 2]:
        return None
    if not all(char in "0123456789" for char in "".join(parts)):
        return None
    year, month, day = [int(part) for part in parts]
    if not 1 <= month <= 12:
        return None
    value = Day.from_ymd(year, month, day)
    # Round trip rejects days that do not exist, e.g. 2026-02-30.
    return value if value.ymd() == (year, month, day) else None


def parse_date(name, raw):
    if is_unset(raw):
        raise ParamError("required", name, "%s is required (YYYY-MM-DD)." % name)
    value = parse_iso_day(to_text(raw).strip())
    if value is None:
        raise ParamError("invalid_date", name, "%s must be YYYY-MM-DD." % name)
    return value


def parse_int(name, raw, default, minimum, maximum):
    if is_unset(raw):
        return default
    text = to_text(raw).strip()
    if not text.isdigit():
        raise ParamError("invalid_integer", name, "%s must be an integer." % name)
    value = int(text)
    if value < minimum or value > maximum:
        raise ParamError(
            "out_of_range", name, "%s must be between %d and %d." % (name, minimum, maximum)
        )
    return value


def parse_list(name, raw, kind, max_items):
    if is_unset(raw):
        return []
    values = []
    for item in to_text(raw).split(","):
        item = item.strip()
        if not item:
            continue
        if kind == "int":
            if not item.isdigit():
                raise ParamError("invalid_integer", name, "%s accepts integers only." % name)
            item = int(item)
        else:
            item = item.upper()
        if item not in values:
            values.append(item)
    if len(values) > max_items:
        raise ParamError(
            "too_many_values", name, "%s accepts at most %d values." % (name, max_items)
        )
    return values


def parse_fields(raw, field_types, default_fields, key_fields):
    """Requested fields, validated against field_types; key fields always first."""
    if is_unset(raw):
        return list(default_fields)
    fields = []
    for item in to_text(raw).split(","):
        item = item.strip().lower()
        if not item:
            continue
        if item not in field_types:
            raise ParamError("unknown_field", "fields", "Unknown field: %s." % item)
        if item not in fields:
            fields.append(item)
    for index, key in enumerate(key_fields):
        if key not in fields:
            fields.insert(index, key)
    return fields


def add_in_filter(clauses, binds, obj, attribute, values):
    """Append "attribute in (:n, ...)" with one bind per value."""
    placeholders = []
    for value in values:
        binds.append((obj, attribute.upper(), value))
        placeholders.append(":%d" % len(binds))
    clauses.append("%s in (%s)" % (attribute, ", ".join(placeholders)))


def parse_text(raw):
    """Search words (upper case), each must appear in the description; [] if unset."""
    if is_unset(raw):
        return []
    text = to_text(raw).strip()
    if len(text) > MAX_TEXT_LENGTH:
        raise ParamError(
            "out_of_range", "text", "text accepts at most %d characters." % MAX_TEXT_LENGTH
        )
    if "%" in text or "_" in text:
        # Would act as LIKE wildcards; escape syntax differs between databases.
        raise ParamError("invalid_text", "text", "text must not contain % or _.")
    words = []
    for word in text.upper().split():
        if len(word) < MIN_WORD_LENGTH:
            raise ParamError(
                "invalid_text",
                "text",
                "Each word in text needs at least %d characters." % MIN_WORD_LENGTH,
            )
        if word not in words:
            words.append(word)
    if len(words) > MAX_TEXT_WORDS:
        raise ParamError(
            "too_many_values", "text", "text accepts at most %d words." % MAX_TEXT_WORDS
        )
    return words


def add_text_filter(clauses, binds, obj, words):
    """Append one "upper(description) like :n" per word, wildcards in the bind."""
    for word in words:
        binds.append((obj, "DESCRIPTION", "%" + word + "%"))
        clauses.append(TEXT_WHERE % len(binds))


def add_site_auth(clauses, binds, userid):
    binds.append(("GROUPUSER", "USERID", userid))
    binds.append(("GROUPUSER", "USERID", userid))
    clauses.append(SITE_AUTH_WHERE % (len(binds) - 1, len(binds)))


def permission_binds(app, option, userid):
    return [
        ("APPLICATIONAUTH", "APP", app),
        ("APPLICATIONAUTH", "OPTIONNAME", option),
        ("GROUPUSER", "USERID", userid),
    ]


def paging(page, page_size, total, returned):
    total_pages = (total + page_size - 1) // page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "returned": returned,
        "has_more": page < total_pages,
    }


def error_response(code, parameter, message):
    return {"error": {"code": code, "parameter": parameter, "message": message}}


def collect_params(param_names, variables, body, query_param):
    """Read each parameter from literal variable, JSON body or query string.

    How the MCP Server delivers arguments is not confirmed yet, so the first source
    with a value wins. Returns (raw, sources); sources holds names, never values.
    """
    raw = {}
    sources = {}
    for name in param_names:
        value = variables.get(name)
        source = "variable"
        if is_unset(value) and body:
            value = body.get(name)
            source = "body"
        if is_unset(value) and query_param is not None:
            value = query_param(name)
            source = "query"
        raw[name] = value
        if not is_unset(value):
            sources[name] = source
    return raw, sources


# Maximo runtime (Jython only) ------------------------------------------------


def to_json(value):
    from com.ibm.json.java import JSONArray, JSONObject

    if isinstance(value, dict):
        obj = JSONObject()
        for key in value:
            obj.put(key, to_json(value[key]))
        return obj
    if isinstance(value, list):
        arr = JSONArray()
        for item in value:
            arr.add(to_json(item))
        return arr
    return value


def read_body(body):
    """Parse requestBody (String or byte[]) into a dict; None if absent or not JSON."""
    if body is None:
        return None
    try:
        from com.ibm.json.java import JSONObject

        if not hasattr(body, "strip"):
            from java.lang import String

            body = String(body, "UTF-8")
        if not body.strip().startswith("{"):
            return None
        obj = JSONObject.parse(body)
        return dict((key, obj.get(key)) for key in obj.keySet())
    except Exception:
        return None


def read_item(mbo, fields, field_types, date_format):
    item = {}
    for field in fields:
        kind = field_types[field]
        if mbo.isNull(field):
            item[field] = None
        elif kind == "date":
            item[field] = date_format.format(mbo.getDate(field))
        elif kind == "int":
            item[field] = mbo.getInt(field)
        elif kind == "float":
            item[field] = mbo.getDouble(field)
        elif kind == "bool":
            item[field] = mbo.getBoolean(field)
        else:
            item[field] = mbo.getString(field)
    return item


def format_where(user_info, where, binds):
    """Where clause with bind values set by SqlFormat (never concatenated)."""
    from java.text import SimpleDateFormat
    from psdi.mbo import SqlFormat

    # UserInfo gives SqlFormat the locale/timezone setObject needs.
    sqf = SqlFormat(user_info, where)
    day_format = SimpleDateFormat("yyyy-MM-dd")
    for index, (obj, attribute, value) in enumerate(binds):
        if isinstance(value, Day):
            sqf.setTimestamp(index + 1, day_format.parse(value.isoformat()))
        else:
            sqf.setObject(index + 1, obj, attribute, to_text(value))
    return sqf.format()


def has_permission(user_info, app, option):
    from psdi.server import MXServer

    binds = permission_binds(app, option, user_info.getUserName())
    auth_set = MXServer.getMXServer().getMboSet("APPLICATIONAUTH", user_info)
    try:
        auth_set.setWhere(format_where(user_info, PERMISSION_WHERE, binds))
        return not auth_set.isEmpty()
    finally:
        auth_set.cleanup()


def query_page(user_info, object_name, query, field_types):
    """Run query (where, binds, order_by, fields, offset, page_size): (total, items)."""
    from java.text import SimpleDateFormat
    from psdi.mbo import MboConstants
    from psdi.server import MXServer

    mboset = MXServer.getMXServer().getMboSet(object_name, user_info)
    try:
        mboset.setFlag(MboConstants.DISCARDABLE, True)
        mboset.setWhere(format_where(user_info, query["where"], query["binds"]))
        mboset.setOrderBy(query["order_by"])
        total = mboset.count()  # one SQL count; never call count() again
        items = []
        output_format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss")
        index = query["offset"]
        end = min(total, index + query["page_size"])
        while index < end:
            mbo = mboset.getMbo(index)
            if mbo is None:
                break
            items.append(read_item(mbo, query["fields"], field_types, output_format))
            index += 1
        return total, items
    finally:
        mboset.cleanup()


def main(scope, throwable, script_name, param_names, run):
    """Run the tool against the script scope and return the response dict.

    Everything lives in locals: after the script ends, Maximo calls toString on
    every top-level binding, and a binding holding globals() recurses into
    itself (StackOverflowError -> BMXAA1649E).
    """
    service = scope.get("service")
    req = scope.get("request")
    try:
        raw, sources = collect_params(
            param_names,
            scope,
            read_body(scope.get("requestBody")),
            req.getQueryParam if req is not None else None,
        )
        # No isLoggingEnabled() on ScriptService in MAS 9.2; log_debug filters by level.
        if service is not None:
            service.log_debug(
                "%s implicit vars: %s; param sources: %s"
                % (script_name, [n for n in IMPLICIT_NAMES if scope.get(n) is not None], sources)
            )
        user_info = req.getUserInfo() if req is not None else scope.get("userInfo")
        if user_info is None:
            # Fail closed: never query without the caller's identity.
            return error_response("no_user", None, "Caller identity not available.")
        return run(user_info, raw)
    except ParamError as e:
        return error_response(e.code, e.parameter, e.message)
    except (Exception, throwable) as e:
        # Throwable: Java exceptions (e.g. NullPointerException) may bypass Exception.
        if service is not None:
            service.log_error("%s failed: %s" % (script_name, e))
        return error_response("internal_error", None, "Query failed. See Maximo log.")


# --- END COMMON ---


SCRIPT_NAME = "QUERYSRS"
OBJECT_NAME = "SR"
PERMISSION_APP = "SR"
PERMISSION_OPTION = "READ"

MAX_DATE_RANGE_DAYS = 366
MAX_TICKETIDS = 50
MAX_LIST_VALUES = 20
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
# Long description, work orders or history make each item large: smaller pages.
MAX_DETAIL_PAGE_SIZE = 50
MAX_AUTHORIZED_SITES = 200
# Work orders / status changes read for one page of service requests; above it,
# "workorders_truncated" / "history_truncated" is true.
MAX_WORKORDERS = 500
MAX_HISTORY = 3000

# Full service request text, may hold rich text. Only on request.
LONG_DESCRIPTION = "description_longdescription"

DATE_FIELDS = (
    "reportdate",
    "statusdate",
    "targetstart",
    "targetfinish",
    "actualstart",
    "actualfinish",
    "changedate",
)
DEFAULT_DATE_FIELD = "reportdate"

# Attribute -> output type. Only these attributes can be selected. Standard TICKET
# (SR) attributes only.
FIELD_TYPES = {
    "ticketid": "str",
    "siteid": "str",
    "description": "str",
    "status": "str",
    "statusdate": "date",
    "reportedby": "str",
    "reportdate": "date",
    "affectedperson": "str",
    "ownergroup": "str",
    "owner": "str",
    "assetnum": "str",
    "location": "str",
    "reportedpriority": "int",
    "internalpriority": "int",
    "classstructureid": "str",
    "targetstart": "date",
    "targetfinish": "date",
    "actualstart": "date",
    "actualfinish": "date",
    "changedate": "date",
    "ticketuid": "int",
    LONG_DESCRIPTION: "str",
}
DEFAULT_FIELDS = (
    "ticketid",
    "siteid",
    "description",
    "status",
    "statusdate",
    "reportdate",
    "reportedby",
    "ownergroup",
    "owner",
    "assetnum",
    "location",
    "reportedpriority",
)
KEY_FIELDS = ("ticketid", "siteid")

# Parameter -> (SR attribute, value type, max values).
LIST_FILTERS = (
    ("siteid", "siteid", "str", MAX_LIST_VALUES),
    ("ticketids", "ticketid", "str", MAX_TICKETIDS),
    ("status", "status", "str", MAX_LIST_VALUES),
    ("ownergroup", "ownergroup", "str", MAX_LIST_VALUES),
    ("owner", "owner", "str", MAX_LIST_VALUES),
    ("reportedby", "reportedby", "str", MAX_LIST_VALUES),
    ("priority", "reportedpriority", "int", MAX_LIST_VALUES),
    ("assetnum", "assetnum", "str", MAX_LIST_VALUES),
    ("location", "location", "str", MAX_LIST_VALUES),
)

PARAM_NAMES = (
    "date_from",
    "date_to",
    "date_field",
    "siteid",
    "ticketids",
    "status",
    "ownergroup",
    "owner",
    "reportedby",
    "priority",
    "assetnum",
    "location",
    "text",
    "include_workorders",
    "include_history",
    "fields",
    "page",
    "page_size",
)

FLAG_TRUE = ("Y", "YES", "TRUE", "1")
FLAG_FALSE = ("N", "NO", "FALSE", "0")

# Service requests only (the SR object already filters; repeated as a safeguard).
SR_CLASSES = "select value from synonymdomain where domainid = 'TKCLASS' and maxvalue = 'SR'"
BASE_WHERE = "class in (" + SR_CLASSES + ")"

# Work orders created from the service requests of one page (origrecordid).
WO_FIELD_TYPES = {
    "origrecordid": "str",
    "wonum": "str",
    "siteid": "str",
    "description": "str",
    "status": "str",
    "statusdate": "date",
    "worktype": "str",
    "reportdate": "date",
    "actfinish": "date",
}
WO_FIELDS = tuple(WO_FIELD_TYPES)
WO_WHERE = "origrecordclass in (" + SR_CLASSES + ") and istask = 0 and origrecordid in (%s)"

# Status history (TKSTATUS) read through its owner SR: ad hoc relationship, bound by
# Maximo from the owner, no caller value. Children are read through their owner: a
# child set without owner fails (JOBTASK, homologation 2026-11-03).
HISTORY_RELATION = "$QSRSTATUS"
HISTORY_RELATION_WHERE = "ticketid = :ticketid and class = :class"
HISTORY_ORDER_BY = "changedate"
# Candidates only: TKSTATUS varies by install (Itambe homologation has no OWNER,
# BMXAA4176E, 2026-11-19). read_history keeps the ones the data dictionary has.
HISTORY_FIELD_TYPES = {
    "status": "str",
    "changedate": "date",
    "changeby": "str",
    "ownergroup": "str",
    "owner": "str",
    "memo": "str",
}
HISTORY_FIELDS = tuple(HISTORY_FIELD_TYPES)
HISTORY_OBJECT = "TKSTATUS"


def available_fields(candidates, exists):
    """Candidates this Maximo has, in order (exists(name) -> bool)."""
    return [name for name in candidates if exists(name)]


def attribute_checker(object_name):
    """exists(name): True if object_name has the attribute in this Maximo."""
    from psdi.server import MXServer

    info = MXServer.getMXServer().getMaximoDD().getMboSetInfo(object_name)

    def exists(name):
        return info.getMboValueInfo(name.upper()) is not None

    return exists


def parse_flag(name, raw):
    if is_unset(raw):
        return False
    text = to_text(raw).strip().upper()
    if text in FLAG_TRUE:
        return True
    if text in FLAG_FALSE:
        return False
    raise ParamError("invalid_flag", name, "%s must be Y or N." % name)


def authorized_sites_query(userid):
    """(where, binds) for the SITE rows the user is authorized for."""
    clauses = []
    binds = []
    add_site_auth(clauses, binds, userid)
    return " and ".join(clauses), binds


def build_query(raw, userid, authorized_sites=None):
    """Validate raw parameters and build the where clause with bind values.

    Returns a dict. "binds" is a list of (object, attribute, value) in placeholder
    order; values never go into the where text.

    The date range is required (service requests are movement), except when
    ticketids is given and both dates are omitted: ticketids is capped at
    MAX_TICKETIDS, so the query stays bounded. Without siteid, authorized_sites
    becomes an explicit "siteid in (...)" (same reason as QUERYWORKORDERS). Service
    requests without site are not returned (site authorization).
    """
    ticketids = parse_list("ticketids", raw.get("ticketids"), "str", MAX_TICKETIDS)
    if ticketids and is_unset(raw.get("date_from")) and is_unset(raw.get("date_to")):
        date_from = date_to = None
    else:
        date_from = parse_date("date_from", raw.get("date_from"))
        date_to = parse_date("date_to", raw.get("date_to"))
        if date_to.ordinal < date_from.ordinal:
            raise ParamError("invalid_range", "date_to", "date_to must be on or after date_from.")
        if date_to.ordinal - date_from.ordinal + 1 > MAX_DATE_RANGE_DAYS:
            raise ParamError(
                "range_too_large",
                "date_to",
                "Date range is limited to %d days." % MAX_DATE_RANGE_DAYS,
            )

    date_field = raw.get("date_field")
    date_field = DEFAULT_DATE_FIELD if is_unset(date_field) else to_text(date_field).strip().lower()
    if date_field not in DATE_FIELDS:
        raise ParamError(
            "invalid_date_field",
            "date_field",
            "date_field must be one of: %s." % ", ".join(DATE_FIELDS),
        )

    include_workorders = parse_flag("include_workorders", raw.get("include_workorders"))
    include_history = parse_flag("include_history", raw.get("include_history"))
    fields = parse_fields(raw.get("fields"), FIELD_TYPES, DEFAULT_FIELDS, KEY_FIELDS)
    detail = LONG_DESCRIPTION in fields or include_workorders or include_history
    max_page_size = MAX_DETAIL_PAGE_SIZE if detail else MAX_PAGE_SIZE
    page = parse_int("page", raw.get("page"), 1, 1, 100000)
    page_size = parse_int(
        "page_size", raw.get("page_size"), min(DEFAULT_PAGE_SIZE, max_page_size), 1, max_page_size
    )
    if include_history and "ticketuid" not in fields:
        fields.append("ticketuid")  # reopens each SR to read its status history

    binds = []
    clauses = [BASE_WHERE]
    if date_from is not None:
        # date_to is inclusive: compare with the start of the next day.
        binds.append((OBJECT_NAME, date_field.upper(), date_from))
        binds.append((OBJECT_NAME, date_field.upper(), Day(date_to.ordinal + 1)))
        clauses.append("%s >= :1 and %s < :2" % (date_field, date_field))

    filters = {}
    for name, attribute, kind, max_items in LIST_FILTERS:
        values = parse_list(name, raw.get(name), kind, max_items)
        if values:
            filters[name] = values
            add_in_filter(clauses, binds, OBJECT_NAME, attribute, values)
        elif name == "siteid" and authorized_sites:
            # Not reported in filters: the caller did not ask for these sites.
            add_in_filter(clauses, binds, OBJECT_NAME, attribute, authorized_sites)

    words = parse_text(raw.get("text"))
    if words:
        filters["text"] = words
        add_text_filter(clauses, binds, OBJECT_NAME, words)

    add_site_auth(clauses, binds, userid)

    return {
        "where": " and ".join(clauses),
        "binds": binds,
        "order_by": "%s desc, ticketid" % date_field,
        "date_field": date_field,
        "date_from": date_from.isoformat() if date_from is not None else None,
        "date_to": date_to.isoformat() if date_to is not None else None,
        "filters": filters,
        "fields": fields,
        "include_workorders": include_workorders,
        "include_history": include_history,
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
    }


def build_workorder_query(ticketids, userid):
    """Work orders created from these service requests, in authorized sites only."""
    binds = []
    placeholders = []
    for value in ticketids:
        binds.append(("WORKORDER", "ORIGRECORDID", value))
        placeholders.append(":%d" % len(binds))
    clauses = [WO_WHERE % ", ".join(placeholders)]
    add_site_auth(clauses, binds, userid)
    return {
        "where": " and ".join(clauses),
        "binds": binds,
        "order_by": "origrecordid, wonum",
        "fields": list(WO_FIELDS),
        "offset": 0,
        "page_size": MAX_WORKORDERS,
    }


def build_sr_query(ticketuids):
    """Service requests of one page, reopened to read their history (already authorized)."""
    binds = []
    placeholders = []
    for value in ticketuids:
        binds.append((OBJECT_NAME, "TICKETUID", value))
        placeholders.append(":%d" % len(binds))
    return {"where": "ticketuid in (%s)" % ", ".join(placeholders), "binds": binds}


def attach_workorders(items, rows):
    """Put each work order under its service request ("workorders", [] if none)."""
    by_ticket = {}
    for row in rows:
        ticketid = row.pop("origrecordid")
        by_ticket.setdefault(ticketid, []).append(row)
    for item in items:
        item["workorders"] = by_ticket.get(item["ticketid"], [])


def attach_history(items, by_uid):
    """Put each status history under its service request ("history", [] if none)."""
    for item in items:
        item["history"] = by_uid.get(item["ticketuid"], [])


def build_response(query, total, items, workorders_truncated=False, history_truncated=False):
    response = paging(query["page"], query["page_size"], total, len(items))
    response["date_field"] = query["date_field"]
    response["date_from"] = query["date_from"]
    response["date_to"] = query["date_to"]
    response["filters"] = query["filters"]
    if query["include_workorders"]:
        response["workorders_truncated"] = workorders_truncated
    if query["include_history"]:
        response["history_truncated"] = history_truncated
    response["items"] = items
    return response


def read_history(user_info, ticketuids):
    """Status changes by ticketuid, at most MAX_HISTORY in all: (by_uid, truncated)."""
    from java.text import SimpleDateFormat
    from psdi.mbo import MboConstants
    from psdi.server import MXServer

    query = build_sr_query(ticketuids)
    fields = available_fields(HISTORY_FIELDS, attribute_checker(HISTORY_OBJECT))
    srs = MXServer.getMXServer().getMboSet(OBJECT_NAME, user_info)
    try:
        srs.setFlag(MboConstants.DISCARDABLE, True)
        srs.setWhere(format_where(user_info, query["where"], query["binds"]))
        output_format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss")
        by_uid = {}
        read = 0
        index = 0
        sr = srs.getMbo(index)
        while sr is not None:
            changes = sr.getMboSet(HISTORY_RELATION, "TKSTATUS", HISTORY_RELATION_WHERE)
            changes.setOrderBy(HISTORY_ORDER_BY)
            found = []
            change_index = 0
            change = changes.getMbo(change_index)
            while change is not None:
                if read >= MAX_HISTORY:
                    return by_uid, True
                found.append(read_item(change, fields, HISTORY_FIELD_TYPES, output_format))
                read += 1
                change_index += 1
                change = changes.getMbo(change_index)
            by_uid[sr.getInt("ticketuid")] = found
            index += 1
            sr = srs.getMbo(index)
        return by_uid, False
    finally:
        srs.cleanup()


def run(user_info, raw):
    if not has_permission(user_info, PERMISSION_APP, PERMISSION_OPTION):
        return error_response(
            "not_authorized",
            None,
            "User needs %s access to %s." % (PERMISSION_OPTION, PERMISSION_APP),
        )
    userid = user_info.getUserName()
    sites = read_authorized_sites(user_info, userid)
    if not sites:
        return error_response("not_authorized", "siteid", "User has no authorized site.")
    query = build_query(raw, userid, sites)
    total, items = query_page(user_info, OBJECT_NAME, query, FIELD_TYPES)
    workorders_truncated = False
    history_truncated = False
    if items and query["include_workorders"]:
        wo_query = build_workorder_query([item["ticketid"] for item in items], userid)
        wo_total, rows = query_page(user_info, "WORKORDER", wo_query, WO_FIELD_TYPES)
        workorders_truncated = wo_total > len(rows)
        attach_workorders(items, rows)
    if items and query["include_history"]:
        by_uid, history_truncated = read_history(user_info, [item["ticketuid"] for item in items])
        attach_history(items, by_uid)
    return build_response(query, total, items, workorders_truncated, history_truncated)


def read_authorized_sites(user_info, userid):
    """Site IDs the user is authorized for, sorted, at most MAX_AUTHORIZED_SITES."""
    from psdi.mbo import MboConstants
    from psdi.server import MXServer

    where, binds = authorized_sites_query(userid)
    site_set = MXServer.getMXServer().getMboSet("SITE", user_info)
    try:
        site_set.setFlag(MboConstants.DISCARDABLE, True)
        site_set.setWhere(format_where(user_info, where, binds))
        site_set.setOrderBy("siteid")
        sites = []
        mbo = site_set.getMbo(0)
        while mbo is not None and len(sites) < MAX_AUTHORIZED_SITES:
            sites.append(mbo.getString("siteid"))
            mbo = site_set.getMbo(len(sites))
        return sites
    finally:
        site_set.cleanup()


try:
    from java.lang import System  # noqa: F401  (resolves only under Jython)

    _IN_MAXIMO = True
except ImportError:  # CPython: module imported by tests
    _IN_MAXIMO = False


if _IN_MAXIMO:
    from com.ibm.tivoli.maximo.oslc import OslcUtils
    from java.lang import Throwable

    # No top-level variable may reference globals() (see main).
    responseBody = OslcUtils.jsonToBytes(
        to_json(main(globals(), Throwable, SCRIPT_NAME, PARAM_NAMES, run))
    )
