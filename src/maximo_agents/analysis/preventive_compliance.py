"""Cumprimento de preventivas por mês: concluídas ÷ (concluídas + pendentes).

Funções puras sobre as OS dos tipos preventivos já buscadas
(fetch.fetch_preventive_work_orders). A IA não faz contas.

Regra (por cliente, config [preventive_compliance]): OS dos tipos preventivos emitidas
no mês (reportdate); "concluídas" e "pendentes" são listas de status (padrão: classes
executed + closed / classe open). OS em outros status (ex.: aguardando programação,
canceladas) ficam fora da conta e são contadas à parte. O status é o de hoje.
"""

import datetime

import pandas as pd

from maximo_agents.analysis.config import ClientConfig
from maximo_agents.analysis.issued_executed import month_end, month_range, to_frame

GROUP_BY = ("crew", "worktype", "modality")  # modality: só com config.modality_field


def _pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _numbers(frame: pd.DataFrame, done: list[str], pending: list[str]) -> dict:
    n_done = int(frame["status"].isin(done).sum())
    n_pending = int(frame["status"].isin(pending).sum())
    return {
        "done": n_done,
        "pending": n_pending,
        "compliance_pct": _pct(n_done, n_done + n_pending),
        "excluded": len(frame) - n_done - n_pending,
    }


def compliance_report(
    records: list[dict],
    config: ClientConfig,
    last_month: datetime.date,
    months: int,
    as_of: datetime.date,
    group_by: str = "crew",
) -> dict:
    if group_by not in GROUP_BY:
        raise ValueError(f"group_by must be one of: {', '.join(GROUP_BY)}.")
    if group_by == "modality" and not config.modality_field:
        raise ValueError(f"{config.client_id}: no modality field configured.")
    done = config.compliance_done_list()
    pending = config.compliance_pending_list()
    frame = to_frame(records, config)
    # A busca já filtra os tipos; o filtro aqui protege de dados fora da regra.
    frame = frame[frame["worktype"].isin(config.preventive_worktypes)]

    result_months = []
    for first in month_range(last_month, months):
        month = first.strftime("%Y-%m")
        frame_m = frame[frame["report_month"] == month]
        totals = _numbers(frame_m, done, pending)
        other = frame_m[~frame_m["status"].isin(done + pending)]
        totals["excluded_by_status"] = _status_counts(other["status"])
        groups = {
            str(key): _numbers(group, done, pending)
            for key, group in frame_m.groupby(group_by, sort=False)
        }
        ordered = sorted(
            groups.items(),
            key=lambda kv: (-(kv[1]["done"] + kv[1]["pending"]), kv[0]),
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
        "modality_field": config.modality_field,
        "rule": {
            "worktypes": list(config.preventive_worktypes),
            "month_basis": "reportdate",
            "done_statuses": done,
            "pending_statuses": pending,
            "formula": "done / (done + pending); other statuses excluded",
        },
        "months": result_months,
    }


def _status_counts(statuses: pd.Series) -> dict[str, int]:
    table = statuses.astype("string").fillna("(empty)").value_counts()
    return {str(k): int(v) for k, v in sorted(table.items(), key=lambda kv: (-kv[1], kv[0]))}


def format_compliance_text(report: dict) -> str:
    rule = report["rule"]
    key = f"by_{report['group_by']}"
    title = {
        "crew": f"Equipe ({report['crew_field']})",
        "worktype": "Tipo de trabalho",
        "modality": f"Modalidade ({report['modality_field']})",
    }[report["group_by"]]
    lines = [
        f"Cumprimento de preventivas - {report['client']} - em {report['as_of']}",
        f"Tipos {', '.join(rule['worktypes'])}, emitidas no mês (reportdate).",
        f"Concluídas ({', '.join(rule['done_statuses'])}) ÷ (concluídas + pendentes "
        f"({', '.join(rule['pending_statuses'])})); outros status fora da conta.",
    ]
    for month in report["months"]:
        partial = " (parcial)" if month["partial"] else ""
        totals = month["totals"]
        lines += ["", f"Mês {month['month']}{partial}", f"{title}:"]
        lines.append(f"  {'':<20}{'concl':>7}{'pend':>7}{'%':>7}{'fora':>7}")
        for name, n in [("TOTAL", totals), *month[key].items()]:
            pct = "-" if n["compliance_pct"] is None else f"{n['compliance_pct']:.1f}"
            lines.append(f"  {name:<20}{n['done']:>7}{n['pending']:>7}{pct:>7}{n['excluded']:>7}")
        if totals["excluded_by_status"]:
            excluded = ", ".join(f"{s} {c}" for s, c in totals["excluded_by_status"].items())
            lines.append(f"  Fora da conta: {excluded}")
    return "\n".join(lines)
