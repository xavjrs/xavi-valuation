"""Discounted cash flow valuation on top of the 3-statement forecast.

Conventions
- Unlevered FCF treats IFRS 16 leases as debt (lease liabilities in the bridge, ROU additions as investment) and
  excludes JV income; the JV stake enters the bridge at book value.
- Bridge: EV + equity-method investments - (borrowings + leases - cash) - minorities
          - after-tax debt-like provisions (decommissioning etc.) - after-tax pension deficit.
- Value is struck at the balance-sheet date (31 Dec of BASE_YEAR) with mid-year discounting, then rolled forward to the
  valuation date at the cost of equity, less the dividend paid in the interim (per-share approximation).
- Two terminal methods: Gordon growth (primary) and an exit EV/EBITDA multiple (cross-check).
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import datetime as dt
import numpy as np
import pandas as pd
from model.three_statement import BASE_YEAR


@dataclass
class ValuationInputs:
    risk_free: float
    equity_risk_premium: float
    beta: float
    market_cap_usd_m: float
    debt_usd_m: float                   # borrowings + leases (book), for capital-structure weights
    credit_spread: float = 0.009        # over risk-free, pre-tax cost of debt
    tax_shield_rate: float = 0.25       # marginal rate on interest (not the 36%+ blended upstream rate)
    terminal_growth: float = 0.015
    exit_multiple: float = 5.0          # EV/EBITDA, cross-check method (user judgement, not sourced from peers)
    wacc_override: float | None = None
    deduct_provisions: bool = True
    valuation_date: dt.date = dt.date(2026, 10, 10)


@dataclass
class Bridge:
    """Balance-sheet items at the base date plus per-share market facts."""
    cash: float
    borrowings: float
    leases: float
    nci: float
    jv_investments: float
    provisions: float
    pension_deficit: float
    shares_m: float
    fx_gbpusd: float
    dps_next_usd: float

    @property
    def net_debt(self) -> float:
        return self.borrowings + self.leases - self.cash


def build_bridge(h: pd.DataFrame, shares_m: float, fx: float, dps_next_usd: float) -> Bridge:
    g = lambda k: float(h.loc[k, BASE_YEAR])
    return Bridge(cash=g("cash"), borrowings=g("debt_current") + g("debt_long"), leases=g("lease_liabilities"),
                  nci=g("nci"), jv_investments=g("equity_investments"), provisions=g("provisions_debt_like"),
                  pension_deficit=g("pension_deficit"), shares_m=shares_m, fx_gbpusd=fx, dps_next_usd=dps_next_usd)


def cost_of_equity(v: ValuationInputs) -> float:
    return v.risk_free + v.beta * v.equity_risk_premium


def cost_of_debt_after_tax(v: ValuationInputs) -> float:
    return (v.risk_free + v.credit_spread) * (1 - v.tax_shield_rate)


def wacc(v: ValuationInputs) -> float:
    if v.wacc_override is not None:
        return v.wacc_override
    e, d = v.market_cap_usd_m, v.debt_usd_m
    return (e * cost_of_equity(v) + d * cost_of_debt_after_tax(v)) / (e + d)


def _equity_bridge(ev: float, v: ValuationInputs, b: Bridge) -> dict:
    items = {"enterprise_value": ev, "jv_investments": b.jv_investments, "borrowings": -b.borrowings,
             "leases": -b.leases, "cash": b.cash, "minorities": -b.nci}
    if v.deduct_provisions:
        items["provisions_after_tax"] = -b.provisions * (1 - v.tax_shield_rate)
        items["pension_deficit_after_tax"] = -b.pension_deficit * (1 - v.tax_shield_rate)
    items["equity_value"] = sum(items.values())
    return items


def _per_share(equity: float, v: ValuationInputs, b: Bridge) -> tuple[float, float, float]:
    f = (v.valuation_date - dt.date(BASE_YEAR, 12, 31)).days / 365
    usd = equity / b.shares_m * (1 + cost_of_equity(v)) ** f - b.dps_next_usd * f
    return usd, usd / b.fx_gbpusd * 100, f


def pv_of_flows(ufcf: np.ndarray, rate: float) -> float:
    t = np.arange(len(ufcf)) + 0.5
    return float((ufcf / (1 + rate) ** t).sum())


def dcf(out: dict[str, pd.DataFrame], v: ValuationInputs, b: Bridge) -> dict:
    u = out["kpis"].loc["unlevered_fcf"].astype(float).values
    ebitda_last = float(out["income_statement"].loc["ebitda"].iloc[-1])
    w, ke, g, n = wacc(v), cost_of_equity(v), v.terminal_growth, len(u)
    if w <= g:
        raise ValueError("WACC must exceed terminal growth")
    pv_flows = pv_of_flows(u, w)

    tv_g = u[-1] * (1 + g) / (w - g)
    pv_tv_g = tv_g / (1 + w) ** (n - 0.5)             # Gordon TV consistent with mid-year flows
    ev_g = pv_flows + pv_tv_g
    br_g = _equity_bridge(ev_g, v, b)
    usd_g, gbp_g, f = _per_share(br_g["equity_value"], v, b)

    tv_m = v.exit_multiple * ebitda_last
    pv_tv_m = tv_m / (1 + w) ** n
    ev_m = pv_flows + pv_tv_m
    br_m = _equity_bridge(ev_m, v, b)
    usd_m, gbp_m, _ = _per_share(br_m["equity_value"], v, b)

    implied_g_from_multiple = (tv_m * w - u[-1]) / (tv_m + u[-1])
    return dict(
        wacc=w, cost_of_equity=ke, terminal_growth=g, pv_flows=pv_flows, pv_terminal=pv_tv_g, ev=ev_g,
        tv_share_of_ev=pv_tv_g / ev_g, implied_exit_ev_ebitda=tv_g / ebitda_last, bridge=br_g,
        equity_value=br_g["equity_value"], value_per_share_usd=usd_g, value_per_share_gbp_pence=gbp_g,
        roll_forward_years=f,
        multiple_method=dict(exit_multiple=v.exit_multiple, ev=ev_m, equity_value=br_m["equity_value"],
                             value_per_share_usd=usd_m, value_per_share_gbp_pence=gbp_m,
                             implied_perpetual_growth=implied_g_from_multiple, bridge=br_m))


def sensitivity(out, v, b, waccs: list[float], growths: list[float]) -> pd.DataFrame:
    rows = {w: [dcf(out, replace(v, wacc_override=w, terminal_growth=g), b)["value_per_share_gbp_pence"]
                for g in growths] for w in waccs}
    df = pd.DataFrame(rows, index=growths).T
    df.index = [f"{w:.2%}" for w in df.index]
    return df.rename_axis("WACC").rename(columns=lambda g: f"g={g:.1%}")
