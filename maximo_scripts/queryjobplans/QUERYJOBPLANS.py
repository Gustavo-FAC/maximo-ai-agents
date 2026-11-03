# QUERYJOBPLANS - read-only job plan query, published as an MCP tool.
#
# Maximo Manage automation script without launch point, language Jython 2.7.
# Source of truth: maximo_scripts/queryjobplans/. Never edit directly in Maximo.
#
# Code must run on Jython 2.7 and CPython 3: the pure functions below (parsing,
# validation, where clause) are tested by tests/unit/test_queryjobplans.py.
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

SCRIPT_NAME = "QUERYJOBPLANS"
OBJECT_NAME = "JOBPLAN"
PERMISSION_APP = "JOBPLAN"
PERMISSION_OPTION = "READ"

MAX_JPNUMS = 50
MAX_LIST_VALUES = 20
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
# Tasks and long descriptions make each item large: smaller pages.
MAX_DETAIL_PAGE_SIZE = 50
# Tasks read for one page of job plans; above it, "tasks_truncated" is true.
MAX_TASKS = 2000

# Procedure text, up to 32000 characters (may hold rich text).
LONG_DESCRIPTION = "description_longdescription"

# Attribute -> output type. Only these attributes can be selected. Standard JOBPLAN
# attributes only.
FIELD_TYPES = {
    "jpnum": "str",
    "pluscrevnum": "int",
    "siteid": "str",
    "orgid": "str",
    "description": "str",
    "status": "str",
    "pluscstatusdate": "date",
    "templatetype": "str",
    "jpduration": "float",
    "persongroup": "str",
    "laborcode": "str",
    "crewid": "str",
    "ownergroup": "str",
    "owner": "str",
    "supervisor": "str",
    "priority": "int",
    "downtime": "bool",
    "interruptible": "bool",
    "classstructureid": "str",
    "jobplanid": "int",
    LONG_DESCRIPTION: "str",
}
DEFAULT_FIELDS = (
    "jpnum",
    "pluscrevnum",
    "siteid",
    "description",
    "status",
    "templatetype",
    "jpduration",
    "persongroup",
    "priority",
)
KEY_FIELDS = ("jpnum", "pluscrevnum", "siteid")

# JOBTASK attributes returned with include_tasks.
TASK_FIELD_TYPES = {
    "jptask": "int",
    "tasksequence": "int",
    "description": "str",
    "taskduration": "float",
    "metername": "str",
    "inspformnum": "str",
    "nestedjpnum": "str",
}
TASK_FIELDS = (
    "jptask",
    "tasksequence",
    "description",
    "taskduration",
    "metername",
    "inspformnum",
    "nestedjpnum",
)
# Ad hoc relationship from each JOBPLAN to its tasks (no dependency on the client's
# relationship names). Bound by Maximo from the owner, no caller value.
TASK_RELATION = "$QJPTASKS"
TASK_RELATION_WHERE = "jobplanid = :jobplanid"

# Parameter -> (JOBPLAN attribute, value type, max values).
LIST_FILTERS = (
    ("jpnums", "jpnum", "str", MAX_JPNUMS),
    ("persongroup", "persongroup", "str", MAX_LIST_VALUES),
    ("templatetype", "templatetype", "str", MAX_LIST_VALUES),
)

# Filters on the job plan's links to assets and locations (JPASSETSPLINK).
LINK_FILTERS = ("assetnum", "location")

PARAM_NAMES = (
    "siteid",
    "jpnums",
    "status",
    "assetnum",
    "location",
    "persongroup",
    "templatetype",
    "text",
    "include_tasks",
    "fields",
    "page",
    "page_size",
)

FLAG_TRUE = ("Y", "YES", "TRUE", "1")
FLAG_FALSE = ("N", "NO", "FALSE", "0")

# Without status: active revisions, by internal value (covers client synonyms).
DEFAULT_STATUS = "ACTIVE"
ALL_STATUS = "ALL"
DEFAULT_STATUS_WHERE = (
    "status in (select value from synonymdomain"
    " where domainid = 'JOBPLANSTATUS' and maxvalue = 'ACTIVE')"
)

# Job plans without site (organization or system level) apply to every site.
SITE_FILTER_WHERE = "(siteid is null or siteid in (%s))"

LINK_WHERE = "jobplanid in (select l.jobplanid from jpassetsplink l where l.%s in (%s))"

# Plans of authorized sites; plans without site only from the organizations of
# authorized sites, or at system level (no organization).
JOBPLAN_SITE_AUTH_WHERE = (
    "((siteid is null and (orgid is null or orgid in (select s.orgid from site s where %s))) or %s)"
)


def bind_placeholders(binds, obj, attribute, values):
    """Append one bind per value; return ":n, ..." for an "in (...)" clause."""
    placeholders = []
    for value in values:
        binds.append((obj, attribute, value))
        placeholders.append(":%d" % len(binds))
    return ", ".join(placeholders)


def parse_flag(name, raw):
    if is_unset(raw):
        return False
    text = to_text(raw).strip().upper()
    if text in FLAG_TRUE:
        return True
    if text in FLAG_FALSE:
        return False
    raise ParamError("invalid_flag", name, "%s must be Y or N." % name)


def add_status_filter(clauses, binds, filters, raw):
    values = parse_list("status", raw, "str", MAX_LIST_VALUES)
    if not values:
        filters["status"] = [DEFAULT_STATUS]
        clauses.append(DEFAULT_STATUS_WHERE)
        return
    if ALL_STATUS in values:
        if len(values) > 1:
            raise ParamError(
                "invalid_status", "status", "ALL cannot be combined with other status values."
            )
        filters["status"] = [ALL_STATUS]
        return
    filters["status"] = values
    add_in_filter(clauses, binds, OBJECT_NAME, "status", values)


def add_jobplan_site_auth(clauses, binds, userid):
    auth = []
    for _ in range(2):
        binds.append(("GROUPUSER", "USERID", userid))
        binds.append(("GROUPUSER", "USERID", userid))
        auth.append(SITE_AUTH_WHERE % (len(binds) - 1, len(binds)))
    clauses.append(JOBPLAN_SITE_AUTH_WHERE % (auth[0], auth[1]))


def build_query(raw, userid):
    """Validate raw parameters and build the where clause with bind values.

    Returns a dict. "binds" is a list of (object, attribute, value) in placeholder
    order; values never go into the where text. No filter is required: job plans are
    master data and every response is capped by page_size, with "total" exact.
    """
    include_tasks = parse_flag("include_tasks", raw.get("include_tasks"))
    fields = parse_fields(raw.get("fields"), FIELD_TYPES, DEFAULT_FIELDS, KEY_FIELDS)
    detailed = include_tasks or LONG_DESCRIPTION in fields
    max_page_size = MAX_DETAIL_PAGE_SIZE if detailed else MAX_PAGE_SIZE
    page = parse_int("page", raw.get("page"), 1, 1, 100000)
    page_size = parse_int(
        "page_size", raw.get("page_size"), min(DEFAULT_PAGE_SIZE, max_page_size), 1, max_page_size
    )
    if include_tasks and "jobplanid" not in fields:
        fields.append("jobplanid")  # groups the tasks of each job plan

    binds = []
    clauses = []
    filters = {}
    sites = parse_list("siteid", raw.get("siteid"), "str", MAX_LIST_VALUES)
    if sites:
        filters["siteid"] = sites
        clauses.append(SITE_FILTER_WHERE % bind_placeholders(binds, OBJECT_NAME, "SITEID", sites))

    for name, attribute, kind, max_items in LIST_FILTERS:
        values = parse_list(name, raw.get(name), kind, max_items)
        if values:
            filters[name] = values
            add_in_filter(clauses, binds, OBJECT_NAME, attribute, values)

    add_status_filter(clauses, binds, filters, raw.get("status"))

    for name in LINK_FILTERS:
        values = parse_list(name, raw.get(name), "str", MAX_LIST_VALUES)
        if values:
            filters[name] = values
            placeholders = bind_placeholders(binds, "JPASSETSPLINK", name.upper(), values)
            clauses.append(LINK_WHERE % (name, placeholders))

    words = parse_text(raw.get("text"))
    if words:
        filters["text"] = words
        add_text_filter(clauses, binds, OBJECT_NAME, words)

    add_jobplan_site_auth(clauses, binds, userid)

    return {
        "where": " and ".join(clauses),
        "binds": binds,
        "order_by": "jpnum, pluscrevnum, siteid",
        "filters": filters,
        "fields": fields,
        "include_tasks": include_tasks,
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
    }


def build_plan_query(jobplanids):
    """Job plans of one page, reopened to read their tasks (ids already authorized)."""
    binds = []
    placeholders = bind_placeholders(binds, OBJECT_NAME, "JOBPLANID", jobplanids)
    return {"where": "jobplanid in (%s)" % placeholders, "binds": binds}


def attach_tasks(items, by_plan):
    """Put each task list under its job plan ("tasks", [] if none)."""
    for item in items:
        item["tasks"] = by_plan.get(item["jobplanid"], [])


def build_response(query, total, items, tasks_truncated=False):
    response = paging(query["page"], query["page_size"], total, len(items))
    response["filters"] = query["filters"]
    if query["include_tasks"]:
        response["tasks_truncated"] = tasks_truncated
    response["items"] = items
    return response


def read_tasks(user_info, jobplanids):
    """Tasks by jobplanid, at most MAX_TASKS in all: (by_plan, truncated).

    JOBTASK must be read through its JOBPLAN: a JOBTASK set without owner fails
    with NullPointerException ("parent" is null; homologation, 2026-11-03).
    """
    from java.text import SimpleDateFormat
    from psdi.mbo import MboConstants
    from psdi.server import MXServer

    query = build_plan_query(jobplanids)
    plans = MXServer.getMXServer().getMboSet(OBJECT_NAME, user_info)
    try:
        plans.setFlag(MboConstants.DISCARDABLE, True)
        plans.setWhere(format_where(user_info, query["where"], query["binds"]))
        output_format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss")
        by_plan = {}
        read = 0
        index = 0
        plan = plans.getMbo(index)
        while plan is not None:
            tasks = plan.getMboSet(TASK_RELATION, "JOBTASK", TASK_RELATION_WHERE)
            tasks.setOrderBy("jptask")
            found = []
            task_index = 0
            task = tasks.getMbo(task_index)
            while task is not None:
                if read >= MAX_TASKS:
                    return by_plan, True
                found.append(read_item(task, TASK_FIELDS, TASK_FIELD_TYPES, output_format))
                read += 1
                task_index += 1
                task = tasks.getMbo(task_index)
            by_plan[plan.getInt("jobplanid")] = found
            index += 1
            plan = plans.getMbo(index)
        return by_plan, False
    finally:
        plans.cleanup()


def run(user_info, raw):
    if not has_permission(user_info, PERMISSION_APP, PERMISSION_OPTION):
        return error_response(
            "not_authorized",
            None,
            "User needs %s access to %s." % (PERMISSION_OPTION, PERMISSION_APP),
        )
    query = build_query(raw, user_info.getUserName())
    total, items = query_page(user_info, OBJECT_NAME, query, FIELD_TYPES)
    truncated = False
    if query["include_tasks"] and items:
        by_plan, truncated = read_tasks(user_info, [item["jobplanid"] for item in items])
        attach_tasks(items, by_plan)
    return build_response(query, total, items, truncated)


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
