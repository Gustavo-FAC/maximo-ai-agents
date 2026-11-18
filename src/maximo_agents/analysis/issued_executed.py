"""OS emitidas × executadas por mês, por equipe ou tipo de trabalho.

Funções puras sobre as OS já buscadas (fetch.fetch_issued_and_finished). A IA não faz
contas: o relatório sai daqui pronto, serializável em JSON.

Duas leituras, porque o cliente pode calcular de um jeito ou de outro:
- Coorte: das OS emitidas no mês (reportdate), quantas já estão executadas (classe
  executed ou closed hoje) e quantas terminaram no próprio mês (actfinish no mês).
  Percentual sobre as emitidas menos as canceladas.
- Fluxo: OS executadas no mês (actfinish no mês, classe executed ou closed hoje),
  emitidas em qualquer mês, comparadas às emitidas no mês. Pode passar de 100%.
Canceladas (classe cancelled) nunca contam como executadas, mesmo com actfinish.
"""

import datetime

import pandas as pd

from maximo_agents.analysis.backlog import EMPTY
from maximo_agents.analysis.config import CANCELLED, CLOSED, EXECUTED, OPEN, ClientConfig
from maximo_agents.analysis.fetch import ISSUED_FIELDS

GROUP_BY = ("crew", "worktype")
DONE = (EXECUTED, CLOSED)
MAX_MONTHS = 12


def month_start(day: datetime.date) -> datetime.date:
    return day.replace(day=1)


def month_end(day: datetime.date) -> datetime.date:
    following = (day.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return following - datetime.timedelta(days=1)


def month_range(last_month: datetime.date, months: int) -> list[datetime.date]:
    """Primeiro dia de cada mês, do mais antigo ao mês de last_month (inclusive)."""
    if not 1 <= months <= MAX_MONTHS:
        raise ValueError(f"months must be between 1 and {MAX_MONTHS}.")
    firsts = [month_start(last_month)]
    for _ in range(months - 1):
        firsts.insert(0, month_start(firsts[0] - datetime.timedelta(days=1)))
    return firsts


def period(
    last_month: datetime.date, months: int, as_of: datetime.date
) -> tuple[datetime.date, datetime.date]:
    """(primeiro dia, último dia) da busca; o último não passa de as_of."""
    firsts = month_range(last_month, months)
    if firsts[-1] > as_of:
        raise ValueError("The last month starts after the analysis date.")
    return firsts[0], min(month_end(firsts[-1]), as_of)


def to_frame(records: list[dict], config: ClientConfig) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(records, columns=[*ISSUED_FIELDS, config.crew_field])
    frame = frame.rename(columns={config.crew_field: "crew"})
    for column in ("crew", "worktype"):
        frame[column] = frame[column].astype("string").fillna(EMPTY).replace("", EMPTY)
    frame["cls"] = frame["status"].map(config.class_of)
    for column, target in (("reportdate", "report_month"), ("actfinish", "finish_month")):
        frame[target] = pd.to_datetime(frame[column], errors="coerce").dt.strftime("%Y-%m")
    return frame


def _pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _numbers(issued: pd.DataFrame, finished: pd.DataFrame, month: str) -> dict:
    """Contagens de um mês (e de um grupo, se os quadros já vierem filtrados)."""
    cancelled = int((issued["cls"] == CANCELLED).sum())
    valid = len(issued) - cancelled
    done = issued[issued["cls"].isin(DONE)]
    same_month = int((done["finish_month"] == month).sum())
    flow = finished[finished["cls"].isin(DONE)]
    return {
        "issued": len(issued),
        "cancelled": cancelled,
        "open_now": int((issued["cls"] == OPEN).sum()),
        "executed_now": len(done),
        "pct_executed_now": _pct(len(done), valid),
        "executed_same_month": same_month,
        "pct_executed_same_month": _pct(same_month, valid),
        "executed_in_month": len(flow),
        "executed_in_month_issued_before": int((flow["report_month"] < month).sum()),
        "pct_executed_in_month_vs_issued": _pct(len(flow), valid),
    }


def issued_executed_report(
    issued_records: list[dict],
    finished_records: list[dict],
    config: ClientConfig,
    last_month: datetime.date,
    months: int,
    as_of: datetime.date,
    group_by: str = "crew",
) -> dict:
    """issued_records: reportdate no período; finished_records: actfinish no período."""
    if group_by not in GROUP_BY:
        raise ValueError(f"group_by must be one of: {', '.join(GROUP_BY)}.")
    issued = to_frame(issued_records, config)
    finished = to_frame(finished_records, config)

    result_months = []
    for first in month_range(last_month, months):
        month = first.strftime("%Y-%m")
        issued_m = issued[issued["report_month"] == month]
        finished_m = finished[finished["finish_month"] == month]
        totals = _numbers(issued_m, finished_m, month)
        done = issued_m[issued_m["cls"].isin(DONE)]
        totals["executed_now_without_finish_date"] = int(done["actfinish"].isna().sum())

        groups = {}
        for key in sorted(set(issued_m[group_by]) | set(finished_m[group_by])):
            groups[str(key)] = _numbers(
                issued_m[issued_m[group_by] == key],
                finished_m[finished_m[group_by] == key],
                month,
            )
        ordered = sorted(
            groups.items(),
            key=lambda kv: (-kv[1]["issued"], -kv[1]["executed_in_month"], kv[0]),
        )
        result_months.append(
            {
                "month": month,
                "partial": month_end(first) > as_of,
                "totals": totals,
                f"by_{group_by}": dict(ordered),
            }
        )

    return {
        "client": config.client_id,
        "as_of": as_of.isoformat(),
        "group_by": group_by,
        "crew_field": config.crew_field,
        "rule": {
            "issued": "reportdate in the month",
            "executed_statuses": config.statuses_of(*DONE),
            "cancelled_statuses": config.statuses_of(CANCELLED),
            "finish_date_field": "actfinish",
        },
        "months": result_months,
    }


def format_issued_executed_text(report: dict) -> str:
    rule = report["rule"]
    key = f"by_{report['group_by']}"
    title = (
        f"Equipe ({report['crew_field']})" if report["group_by"] == "crew" else "Tipo de trabalho"
    )
    lines = [
        f"OS emitidas x executadas - {report['client']} - em {report['as_of']}",
        f"Emitida: reportdate no mês. Executada: status {', '.join(rule['executed_statuses'])}. "
        f"Canceladas ({', '.join(rule['cancelled_statuses'])}) fora do percentual.",
        "Coorte: das emitidas no mês, executadas hoje (exec) e no próprio mês (mês).",
        "Fluxo: executadas no mês (actfinish), emitidas em qualquer mês; ant. = de meses "
        "anteriores.",
    ]
    header = (
        f"  {'':<20}{'emit':>6}{'canc':>6}{'abert':>6}{'exec':>6}{'%':>7}"
        f"{'mês':>6}{'%':>7}{'fluxo':>7}{'ant.':>6}{'%':>7}"
    )
    for month in report["months"]:
        partial = " (parcial)" if month["partial"] else ""
        totals = month["totals"]
        lines += [
            "",
            f"Mês {month['month']}{partial} - executadas sem actfinish: "
            f"{totals['executed_now_without_finish_date']}",
            f"{title}:",
            header,
        ]
        for name, n in [("TOTAL", totals), *month[key].items()]:
            lines.append(
                f"  {name:<20}{n['issued']:>6}{n['cancelled']:>6}{n['open_now']:>6}"
                f"{n['executed_now']:>6}{_fmt(n['pct_executed_now']):>7}"
                f"{n['executed_same_month']:>6}{_fmt(n['pct_executed_same_month']):>7}"
                f"{n['executed_in_month']:>7}{n['executed_in_month_issued_before']:>6}"
                f"{_fmt(n['pct_executed_in_month_vs_issued']):>7}"
            )
    return "\n".join(lines)


def _fmt(pct: float | None) -> str:
    return "-" if pct is None else f"{pct:.1f}"
