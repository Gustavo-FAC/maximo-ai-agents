"""Consumo de material: custo e quantidade por item, ativo, location, OS e tipo.

Funções puras sobre as transações do MATUSETRANS (fetch.fetch_material_usage) e as
OS delas (fetch.fetch_work_orders_by_number). Sinais do Maximo: quantity negativa na
baixa e positiva na devolução; linecost o contrário. Consumo líquido =
-soma(quantity); custo líquido = soma(linecost). Ativo e location: os da transação
ou, se vazios, os da OS.
"""

import datetime

import pandas as pd

from maximo_agents.analysis.backlog import EMPTY
from maximo_agents.analysis.config import ClientConfig
from maximo_agents.analysis.fetch import MATERIAL_FIELDS, WORK_ORDER_LOOKUP_FIELDS
from maximo_agents.analysis.recurrence import has_value

DEFAULT_TOP = 20
NO_WORK_ORDER = "(sem OS)"
WORK_ORDER_NOT_FOUND = "(OS não encontrada)"  # ex.: tarefa, que o QUERYWORKORDERS não traz
PARETO_SHARE = 0.8


def to_frame(transactions: list[dict], work_orders: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(transactions, columns=list(MATERIAL_FIELDS))
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0.0)
    frame["linecost"] = pd.to_numeric(frame["linecost"], errors="coerce").fillna(0.0)
    frame["used"] = -frame["quantity"]
    frame["is_return"] = frame["quantity"] > 0
    frame["when"] = pd.to_datetime(frame["actualdate"], errors="coerce")
    frame["refwo"] = frame["refwo"].astype("string")

    orders = pd.DataFrame.from_records(work_orders, columns=list(WORK_ORDER_LOOKUP_FIELDS))
    orders = orders.drop_duplicates(["siteid", "wonum"]).rename(
        columns={
            "wonum": "refwo",
            "description": "wo_description",
            "worktype": "wo_worktype",
            "assetnum": "wo_assetnum",
            "location": "wo_location",
        }
    )
    orders["refwo"] = orders["refwo"].astype("string")
    frame = frame.merge(orders, on=["siteid", "refwo"], how="left", indicator=True)

    has_wo = has_value(frame["refwo"])
    found = frame["_merge"] == "both"
    worktype = frame["wo_worktype"].astype("string")
    worktype = worktype.where(has_value(worktype), EMPTY)
    return frame.assign(
        has_wo=has_wo,
        found=found,
        worktype=worktype.where(found, WORK_ORDER_NOT_FOUND).where(has_wo, NO_WORK_ORDER),
        asset=frame["assetnum"].where(has_value(frame["assetnum"]), frame["wo_assetnum"]),
        place=frame["location"].where(has_value(frame["location"]), frame["wo_location"]),
    ).drop(columns="_merge")


def item_stats(frame: pd.DataFrame, total: float, top: int) -> tuple[list[dict], dict]:
    data = frame[has_value(frame["itemnum"])]
    table = (
        data.assign(issue=~data["is_return"])
        .groupby("itemnum", sort=False)
        .agg(
            net_cost=("linecost", "sum"),
            net_quantity=("used", "sum"),
            issues=("issue", "sum"),
            returns=("is_return", "sum"),
            work_orders=("refwo", "nunique"),
            assets=("asset", "nunique"),
            description=("description", "last"),
            unit=("issueunit", "last"),
        )
        .reset_index()
        .sort_values(["net_cost", "itemnum"], ascending=[False, True], kind="stable")
    )
    positive = table.loc[table["net_cost"] > 0, "net_cost"]
    cumulative = positive.cumsum() / positive.sum() if len(positive) else positive
    pareto = {
        "items_with_cost": len(positive),
        "items_for_80pct": int((cumulative < PARETO_SHARE).sum()) + 1 if len(positive) else 0,
    }
    rows = [
        {
            "itemnum": row.itemnum,
            "description": _value(row.description),
            "unit": _value(row.unit),
            "net_quantity": round(float(row.net_quantity), 3),
            "net_cost": _money(row.net_cost),
            "share": _share(row.net_cost, total),
            "issues": int(row.issues),
            "returns": int(row.returns),
            "work_orders": int(row.work_orders),
            "assets": int(row.assets),
        }
        for row in table.head(top).itertuples(index=False)
    ]
    return rows, pareto


def object_stats(frame: pd.DataFrame, column: str, key: str, total: float, top: int) -> dict:
    """Custo por ativo ou location (site + código), com o item de maior custo."""
    data = frame[has_value(frame[column])]
    table = (
        data.groupby(["siteid", column], sort=False)
        .agg(
            net_cost=("linecost", "sum"),
            transactions=("linecost", "size"),
            work_orders=("refwo", "nunique"),
            items=("itemnum", "nunique"),
        )
        .reset_index()
        .sort_values(["net_cost", column], ascending=[False, True], kind="stable")
    )
    rows = []
    for row in table.head(top).itertuples(index=False):
        siteid, value = row.siteid, getattr(row, column)
        own = data[(data["siteid"] == siteid) & (data[column] == value)]
        by_item = own.groupby("itemnum")["linecost"].sum()
        top_item = by_item.idxmax() if len(by_item) else None
        description = own.loc[own["itemnum"] == top_item, "description"].dropna()
        rows.append(
            {
                key: value,
                "siteid": siteid,
                "net_cost": _money(row.net_cost),
                "share": _share(row.net_cost, total),
                "transactions": int(row.transactions),
                "work_orders": int(row.work_orders),
                "items": int(row.items),
                "top_item": top_item,
                "top_item_description": description.iloc[-1] if len(description) else None,
            }
        )
    return {"objects": len(table), "net_cost": _money(data["linecost"].sum()), "top": rows}


def work_order_stats(frame: pd.DataFrame, total: float, top: int) -> list[dict]:
    data = frame[frame["has_wo"]]
    table = (
        data.groupby(["siteid", "refwo"], sort=False)
        .agg(
            net_cost=("linecost", "sum"),
            transactions=("linecost", "size"),
            items=("itemnum", "nunique"),
            worktype=("worktype", "first"),
            asset=("asset", "first"),
            description=("wo_description", "first"),
        )
        .reset_index()
        .sort_values(["net_cost", "refwo"], ascending=[False, True], kind="stable")
    )
    return [
        {
            "wonum": row.refwo,
            "siteid": row.siteid,
            "net_cost": _money(row.net_cost),
            "share": _share(row.net_cost, total),
            "transactions": int(row.transactions),
            "items": int(row.items),
            "worktype": row.worktype,
            "assetnum": _value(row.asset),
            "description": _value(row.description),
        }
        for row in table.head(top).itertuples(index=False)
    ]


def material_report(
    transactions: list[dict],
    work_orders: list[dict],
    config: ClientConfig,
    date_from: datetime.date,
    date_to: datetime.date,
    top: int = DEFAULT_TOP,
) -> dict:
    frame = to_frame(transactions, work_orders)
    total = float(frame["linecost"].sum())
    returns = frame["is_return"]
    no_wo = ~frame["has_wo"]
    no_asset = ~has_value(frame["asset"])

    by_worktype = frame.groupby("worktype").agg(
        net_cost=("linecost", "sum"),
        transactions=("linecost", "size"),
        work_orders=("refwo", "nunique"),
    )
    by_worktype = by_worktype.sort_values("net_cost", ascending=False, kind="stable")
    storeroom = frame["storeloc"].astype("string")
    storeroom = storeroom.where(has_value(storeroom), EMPTY)
    by_storeroom = frame.groupby(storeroom)["linecost"].sum().sort_values(ascending=False)

    months = {str(m): {"net_cost": 0.0, "transactions": 0} for m in _months(date_from, date_to)}
    monthly = frame.groupby(frame["when"].dt.to_period("M").astype(str))["linecost"]
    for month, cost in monthly.sum().items():
        if month in months:
            months[month] = {"net_cost": _money(cost), "transactions": int(monthly.size()[month])}

    items, pareto = item_stats(frame, total, top)
    return {
        "client": config.client_id,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "date_field": "actualdate",
        "transactions": len(frame),
        "issues": int((~returns).sum()),
        "returns": int(returns.sum()),
        "issued_cost": _money(frame.loc[~returns, "linecost"].sum()),
        "returned_cost": _money(-frame.loc[returns, "linecost"].sum()),
        "net_cost": _money(total),
        "items": int(frame["itemnum"].nunique()),
        "work_orders": len(frame.loc[frame["has_wo"], ["siteid", "refwo"]].drop_duplicates()),
        "work_orders_not_found": len(
            frame.loc[frame["has_wo"] & ~frame["found"], ["siteid", "refwo"]].drop_duplicates()
        ),
        "without_work_order": {
            "transactions": int(no_wo.sum()),
            "net_cost": _money(frame.loc[no_wo, "linecost"].sum()),
        },
        "without_asset": {
            "transactions": int(no_asset.sum()),
            "net_cost": _money(frame.loc[no_asset, "linecost"].sum()),
        },
        "by_month": months,
        "by_worktype": {
            str(worktype): {
                "net_cost": _money(row.net_cost),
                "share": _share(row.net_cost, total),
                "transactions": int(row.transactions),
                "work_orders": int(row.work_orders),
            }
            for worktype, row in by_worktype.iterrows()
        },
        "by_storeroom": {str(k): _money(v) for k, v in by_storeroom.items()},
        "pareto": pareto,
        "by_item": items,
        "by_asset": object_stats(frame, "asset", "assetnum", total, top),
        "by_location": object_stats(frame, "place", "location", total, top),
        "by_work_order": work_order_stats(frame, total, top),
    }


def format_material_text(report: dict) -> str:
    pareto = report["pareto"]
    lines = [
        f"Consumo de material - {report['client']} - {report['date_from']} a "
        f"{report['date_to']} (actualdate)",
        "Custo líquido = baixas - devoluções. Ativo/location da transação ou, se vazio, da OS.",
        "",
        f"Custo líquido: {_brl(report['net_cost'])} (baixas {_brl(report['issued_cost'])}, "
        f"devoluções {_brl(report['returned_cost'])})",
        f"Transações: {report['transactions']} ({report['issues']} baixas, "
        f"{report['returns']} devoluções); itens: {report['items']}; OS: "
        f"{report['work_orders']} (não encontradas: {report['work_orders_not_found']})",
        f"Sem OS: {report['without_work_order']['transactions']} transações, "
        f"{_brl(report['without_work_order']['net_cost'])}. Sem ativo: "
        f"{report['without_asset']['transactions']} transações, "
        f"{_brl(report['without_asset']['net_cost'])}.",
        f"Pareto: {pareto['items_for_80pct']} de {pareto['items_with_cost']} itens com custo "
        "fazem 80% do custo.",
        "",
        "Por tipo de trabalho da OS:",
    ]
    for worktype, row in report["by_worktype"].items():
        lines.append(
            f"  {worktype:<22}{_brl(row['net_cost']):>16}{row['share']:>7}%"
            f"{row['work_orders']:>7} OS"
        )
    lines += ["", "Por almoxarifado:"]
    lines += [f"  {k:<22}{_brl(v):>16}" for k, v in report["by_storeroom"].items()]
    lines += ["", "Por mês:"]
    lines += [
        f"  {month:<10}{_brl(v['net_cost']):>16}{v['transactions']:>7} transações"
        for month, v in report["by_month"].items()
    ]
    lines += [
        "",
        "== ITENS (maior custo líquido)",
        f"  {'item':<15}{'custo':>15}{'%':>7}{'qtd líq.':>11} {'un':<4}{'OS':>5}  descrição",
    ]
    for row in report["by_item"]:
        lines.append(
            f"  {row['itemnum']!s:<15}{_brl(row['net_cost']):>15}{row['share']:>7}"
            f"{row['net_quantity']:>11g} {row['unit'] or '-'!s:<4}{row['work_orders']:>5}  "
            f"{(row['description'] or '')[:40]}"
        )
    for part, key, title in (
        ("by_asset", "assetnum", "ATIVOS"),
        ("by_location", "location", "LOCATIONS"),
    ):
        block = report[part]
        lines += [
            "",
            f"== {title}: {block['objects']} com consumo, {_brl(block['net_cost'])}",
            f"  {key:<14}{'site':<11}{'custo':>15}{'%':>7}{'OS':>5}{'itens':>6}  "
            "item de maior custo",
        ]
        for row in block["top"]:
            lines.append(
                f"  {row[key]!s:<14}{row['siteid']!s:<11}{_brl(row['net_cost']):>15}"
                f"{row['share']:>7}{row['work_orders']:>5}{row['items']:>6}  "
                f"{(row['top_item_description'] or row['top_item'] or '')[:35]}"
            )
    lines += [
        "",
        "== OS (maior custo líquido)",
        f"  {'OS':<10}{'site':<11}{'custo':>15}{'%':>7} {'tipo':<8}{'ativo':<12}descrição",
    ]
    for row in report["by_work_order"]:
        lines.append(
            f"  {row['wonum']!s:<10}{row['siteid']!s:<11}{_brl(row['net_cost']):>15}"
            f"{row['share']:>7} {row['worktype']!s:<8}{row['assetnum'] or '-'!s:<12}"
            f"{(row['description'] or '')[:40]}"
        )
    return "\n".join(lines)


def _months(date_from: datetime.date, date_to: datetime.date):
    return pd.period_range(date_from, date_to, freq="M")


def _money(value) -> float:
    return round(float(value), 2)


def _share(part: float, whole: float) -> float:
    return round(100 * float(part) / whole, 1) if whole else 0.0


def _value(value):
    return None if value is None or pd.isna(value) else value


def _brl(value: float) -> str:
    """1234.5 -> '1.234,50' (moeda da organização no Maximo, sem símbolo)."""
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
