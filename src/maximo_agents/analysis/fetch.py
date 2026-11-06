"""Busca de dados no Maximo pelas ferramentas de leitura do MCP (todas as páginas).

O chamador da ferramenta é injetado (call_tool): em produção, a sessão MCP; nos
testes, uma função falsa. Argumentos passam por clean_arguments (allowlist).
"""

import datetime
from collections.abc import Awaitable, Callable, Iterable

from maximo_agents.analysis.config import CLOSED, EXECUTED, OPEN, ClientConfig
from maximo_agents.mcp.allowlist import clean_arguments

ToolCaller = Callable[[str, dict[str, str]], Awaitable[dict]]

WORK_ORDER_TOOL = "script_queryworkorders"
STATUS_TOOL = "script_querywostatus"
MAX_DAYS_PER_CALL = 366  # limite do script
MAX_LIST_VALUES = 20  # limite do script por lista
MAX_WONUMS = 50  # limite do QUERYWOSTATUS por chamada
PAGE_SIZE = 500  # máximo do script
DEFAULT_MAX_RECORDS = 50_000

BACKLOG_FIELDS = (
    "wonum",
    "siteid",
    "description",
    "status",
    "statusdate",
    "worktype",
    "wopriority",
    "assetnum",
    "location",
    "persongroup",
    "reportdate",
)


class MaximoToolError(RuntimeError):
    """A ferramenta devolveu erro (objeto 'error' ou falha da chamada)."""

    def __init__(self, code: str, parameter: str | None, message: str):
        super().__init__(f"{code}: {message}" + (f" (parameter {parameter})" if parameter else ""))
        self.code = code
        self.parameter = parameter


class TooManyRecordsError(RuntimeError):
    """A busca passou do limite de registros; estreitar os filtros."""


def date_windows(
    start: datetime.date, end: datetime.date, max_days: int = MAX_DAYS_PER_CALL
) -> list[tuple[datetime.date, datetime.date]]:
    """Divide [start, end] (inclusivo) em janelas de até max_days dias."""
    if end < start:
        raise ValueError("end must be on or after start.")
    windows = []
    current = start
    while current <= end:
        last = min(current + datetime.timedelta(days=max_days - 1), end)
        windows.append((current, last))
        current = last + datetime.timedelta(days=1)
    return windows


def chunks(values: list[str], size: int = MAX_LIST_VALUES) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)] or [[]]


async def fetch_work_orders(
    call_tool: ToolCaller,
    *,
    date_from: datetime.date,
    date_to: datetime.date,
    filters: dict[str, list[str]],
    fields: Iterable[str],
    date_field: str = "reportdate",
    max_records: int = DEFAULT_MAX_RECORDS,
) -> list[dict]:
    """Todas as OS do período (janelas de 366 dias, todas as páginas), sem repetição."""
    check_filters(filters)
    seen: set[tuple] = set()
    records: list[dict] = []
    for window_from, window_to in date_windows(date_from, date_to):
        arguments = {
            "date_from": window_from.isoformat(),
            "date_to": window_to.isoformat(),
            "date_field": date_field,
            "fields": ",".join(fields),
        }
        arguments.update(joined(filters))
        await fetch_all_pages(
            call_tool, WORK_ORDER_TOOL, arguments, ("siteid", "wonum"), seen, records, max_records
        )
    return records


def check_filters(filters: dict[str, list[str]]) -> None:
    for name, values in filters.items():
        if len(values) > MAX_LIST_VALUES:
            raise ValueError(f"Filter '{name}' has more than {MAX_LIST_VALUES} values.")


def joined(filters: dict[str, list[str]]) -> dict[str, str]:
    """Listas viram texto separado por vírgula; lista vazia não vai."""
    return {k: ",".join(v) for k, v in filters.items() if v}


def raise_on_error(response: dict) -> None:
    error = response.get("error")
    if error:
        raise MaximoToolError(
            str(error.get("code")), error.get("parameter"), str(error.get("message"))
        )


async def fetch_all_pages(
    call_tool: ToolCaller,
    tool: str,
    arguments: dict[str, str],
    key_fields: tuple[str, ...],
    seen: set[tuple],
    records: list[dict],
    max_records: int,
) -> None:
    """Acrescenta a records todas as páginas da chamada, sem repetir a chave."""
    page = 1
    while True:
        page_arguments = {**arguments, "page": str(page), "page_size": str(PAGE_SIZE)}
        response = await call_tool(tool, clean_arguments(tool, page_arguments))
        raise_on_error(response)
        for item in response.get("items") or []:
            # A página pode repetir registros se os dados mudarem durante a busca.
            key = tuple(item.get(field) for field in key_fields)
            if key not in seen:
                seen.add(key)
                records.append(item)
        if len(records) > max_records:
            raise TooManyRecordsError(f"More than {max_records} records; narrow the filters.")
        if not response.get("has_more"):
            break
        page += 1


async def count_work_orders(
    call_tool: ToolCaller,
    *,
    date_from: datetime.date,
    date_to: datetime.date,
    filters: dict[str, list[str]],
    date_field: str = "reportdate",
) -> int:
    """Total de OS do período (soma do 'total' de cada janela; 1 item por chamada)."""
    total = 0
    for window_from, window_to in date_windows(date_from, date_to):
        arguments = {
            "date_from": window_from.isoformat(),
            "date_to": window_to.isoformat(),
            "date_field": date_field,
            "fields": "wonum",
            "page_size": "1",
        }
        arguments.update(joined(filters))
        response = await call_tool(WORK_ORDER_TOOL, clean_arguments(WORK_ORDER_TOOL, arguments))
        raise_on_error(response)
        total += int(response.get("total") or 0)
    return total


def status_filters(config: ClientConfig, statuses: list[str]) -> list[dict[str, list[str]]]:
    """Filtros por lote de até 20 status, com os sites do cliente."""
    result = []
    for status_chunk in chunks(statuses):
        filters = {"status": status_chunk}
        if config.sites:
            filters["siteid"] = list(config.sites)
        result.append(filters)
    return result


async def fetch_backlog_work_orders(
    call_tool: ToolCaller,
    config: ClientConfig,
    as_of: datetime.date,
    since: datetime.date | None = None,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> list[dict]:
    """OS abertas do cliente (todas as páginas), de since (ou history_start) até as_of."""
    statuses = config.statuses_of(OPEN)
    if not statuses:
        raise ValueError(f"{config.client_id}: no open status configured.")
    records: list[dict] = []
    for filters in status_filters(config, statuses):
        records.extend(
            await fetch_work_orders(
                call_tool,
                date_from=since or config.history_start,
                date_to=as_of,
                filters=filters,
                fields=BACKLOG_FIELDS,
                max_records=max_records - len(records),
            )
        )
    return records


CORRECTIVE_FIELDS = (
    "wonum",
    "siteid",
    "description",
    "status",
    "worktype",
    "assetnum",
    "location",
    "reportdate",
    "actfinish",
)


async def fetch_corrective_work_orders(
    call_tool: ToolCaller,
    config: ClientConfig,
    date_from: datetime.date,
    date_to: datetime.date,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> list[dict]:
    """OS dos tipos corretivos do cliente no período (pelo reportdate), qualquer status."""
    if not config.corrective_worktypes:
        raise ValueError(f"{config.client_id}: no corrective_worktypes configured.")
    filters = {"worktype": list(config.corrective_worktypes)}
    if config.sites:
        filters["siteid"] = list(config.sites)
    return await fetch_work_orders(
        call_tool,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
        fields=CORRECTIVE_FIELDS,
        max_records=max_records,
    )


async def count_executed_by_age(
    call_tool: ToolCaller,
    config: ClientConfig,
    as_of: datetime.date,
    since: datetime.date | None = None,
) -> dict[str, int]:
    """OS executadas (aguardando fechamento) por faixa de idade, só pelo total."""
    from maximo_agents.analysis.backlog import age_bucket_ranges

    statuses = config.statuses_of(EXECUTED)
    by_age: dict[str, int] = {}
    for label, date_from, date_to in age_bucket_ranges(as_of, since or config.history_start):
        by_age[label] = 0
        for filters in status_filters(config, statuses) if statuses else []:
            by_age[label] += await count_work_orders(
                call_tool, date_from=date_from, date_to=date_to, filters=filters
            )
    return by_age


STATUS_FIELDS = ("wonum", "siteid", "status", "changedate", "changeby", "wostatusid")


async def fetch_completed_histories(
    call_tool: ToolCaller,
    config: ClientConfig,
    date_from: datetime.date,
    date_to: datetime.date,
    worktypes: Iterable[str] = (),
    max_records: int = DEFAULT_MAX_RECORDS,
) -> list[dict]:
    """Histórico completo de status das OS que foram para um status fechado no período.

    1) Mudanças para status da classe 'closed' no período (pelo changedate) dão as OS.
    2) O histórico de cada OS vem por wonums (sem datas), em lotes de 50 por site.
    Se a conclusão foi mesmo no período (e não antes) fica para a análise.
    """
    statuses = config.statuses_of(CLOSED)
    if not statuses:
        raise ValueError(f"{config.client_id}: no closed status configured.")
    worktypes = list(worktypes)
    check_filters({"worktype": worktypes})

    seen: set[tuple] = set()
    completions: list[dict] = []
    for filters in status_filters(config, statuses):
        filters["worktype"] = worktypes
        for window_from, window_to in date_windows(date_from, date_to):
            arguments = {
                "date_from": window_from.isoformat(),
                "date_to": window_to.isoformat(),
                "fields": "wonum,siteid,status,changedate",
            }
            arguments.update(joined(filters))
            await fetch_all_pages(
                call_tool,
                STATUS_TOOL,
                arguments,
                ("siteid", "wonum"),
                seen,
                completions,
                max_records,
            )

    seen = set()
    history: list[dict] = []
    pairs = ((item["siteid"], item["wonum"]) for item in completions)
    for siteid, wonum_chunk in wonum_batches(pairs):
        arguments = {
            "siteid": siteid,
            "wonums": ",".join(wonum_chunk),
            "fields": ",".join(STATUS_FIELDS),
        }
        await fetch_all_pages(
            call_tool,
            STATUS_TOOL,
            arguments,
            ("siteid", "wonum", "wostatusid", "changedate", "status"),
            seen,
            history,
            max_records,
        )
    return history


def wonum_batches(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, list[str]]]:
    """(siteid, wonum) sem repetição, em lotes de até 50 wonums do mesmo site."""
    by_site: dict[str, set[str]] = {}
    for siteid, wonum in pairs:
        if siteid and wonum:
            by_site.setdefault(siteid, set()).add(wonum)
    return [
        (siteid, wonum_chunk)
        for siteid in sorted(by_site)
        for wonum_chunk in chunks(sorted(by_site[siteid]), MAX_WONUMS)
    ]


MATERIAL_TOOL = "script_querymatusage"
MATERIAL_FIELDS = (
    "refwo",
    "siteid",
    "matusetransid",
    "actualdate",
    "itemnum",
    "description",
    "quantity",
    "issueunit",
    "linecost",
    "storeloc",
    "assetnum",
    "location",
)
WORK_ORDER_LOOKUP_FIELDS = ("wonum", "siteid", "description", "worktype", "assetnum", "location")


async def fetch_material_usage(
    call_tool: ToolCaller,
    config: ClientConfig,
    date_from: datetime.date,
    date_to: datetime.date,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> list[dict]:
    """Baixas e devoluções de material no período (actualdate), com ou sem OS."""
    filters = {"siteid": list(config.sites)}
    check_filters(filters)
    seen: set[tuple] = set()
    records: list[dict] = []
    for window_from, window_to in date_windows(date_from, date_to):
        arguments = {
            "date_from": window_from.isoformat(),
            "date_to": window_to.isoformat(),
            "date_field": "actualdate",
            "fields": ",".join(MATERIAL_FIELDS),
        }
        arguments.update(joined(filters))
        await fetch_all_pages(
            call_tool,
            MATERIAL_TOOL,
            arguments,
            ("siteid", "matusetransid"),
            seen,
            records,
            max_records,
        )
    return records


async def fetch_work_orders_by_number(
    call_tool: ToolCaller,
    pairs: Iterable[tuple[str, str]],
    fields: Iterable[str] = WORK_ORDER_LOOKUP_FIELDS,
    max_records: int = DEFAULT_MAX_RECORDS,
) -> list[dict]:
    """OS pedidas por (siteid, wonum), em lotes de 50 por site. Tarefas não vêm."""
    seen: set[tuple] = set()
    records: list[dict] = []
    for siteid, wonum_chunk in wonum_batches(pairs):
        arguments = {"siteid": siteid, "wonums": ",".join(wonum_chunk), "fields": ",".join(fields)}
        await fetch_all_pages(
            call_tool, WORK_ORDER_TOOL, arguments, ("siteid", "wonum"), seen, records, max_records
        )
    return records
