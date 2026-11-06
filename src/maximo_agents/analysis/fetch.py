"""Busca de dados no Maximo pelas ferramentas de leitura do MCP (todas as páginas).

O chamador da ferramenta é injetado (call_tool): em produção, a sessão MCP; nos
testes, uma função falsa. Argumentos passam por clean_arguments (allowlist).
"""

import datetime
from collections.abc import Awaitable, Callable, Iterable

from maximo_agents.analysis.config import EXECUTED, OPEN, ClientConfig
from maximo_agents.mcp.allowlist import clean_arguments

ToolCaller = Callable[[str, dict[str, str]], Awaitable[dict]]

WORK_ORDER_TOOL = "script_queryworkorders"
MAX_DAYS_PER_CALL = 366  # limite do script
MAX_LIST_VALUES = 20  # limite do script por lista
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
    for name, values in filters.items():
        if len(values) > MAX_LIST_VALUES:
            raise ValueError(f"Filter '{name}' has more than {MAX_LIST_VALUES} values.")

    seen: set[tuple] = set()
    records: list[dict] = []
    for window_from, window_to in date_windows(date_from, date_to):
        page = 1
        while True:
            arguments = {
                "date_from": window_from.isoformat(),
                "date_to": window_to.isoformat(),
                "date_field": date_field,
                "fields": ",".join(fields),
                "page": str(page),
                "page_size": str(PAGE_SIZE),
            }
            arguments.update({k: ",".join(v) for k, v in filters.items() if v})
            response = await call_tool(WORK_ORDER_TOOL, clean_arguments(WORK_ORDER_TOOL, arguments))
            error = response.get("error")
            if error:
                raise MaximoToolError(
                    str(error.get("code")), error.get("parameter"), str(error.get("message"))
                )
            for item in response.get("items") or []:
                # A página pode repetir OS se os dados mudarem durante a busca.
                key = (item.get("siteid"), item.get("wonum"))
                if key not in seen:
                    seen.add(key)
                    records.append(item)
            if len(records) > max_records:
                raise TooManyRecordsError(
                    f"More than {max_records} work orders; narrow the filters."
                )
            if not response.get("has_more"):
                break
            page += 1
    return records


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
        arguments.update({k: ",".join(v) for k, v in filters.items() if v})
        response = await call_tool(WORK_ORDER_TOOL, clean_arguments(WORK_ORDER_TOOL, arguments))
        error = response.get("error")
        if error:
            raise MaximoToolError(
                str(error.get("code")), error.get("parameter"), str(error.get("message"))
            )
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
