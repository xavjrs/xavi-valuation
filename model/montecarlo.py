"""Monte Carlo valuation engine.

Unlevered FCF depends only on operating drivers (not on financing), so the whole simulation is vectorised over paths
without re-running the 3-statement loop. `base_path_value` reproduces `dcf()` exactly for zero shocks (tested).

Stochastic drivers (all editable; calibration is judgemental because only 5 annual observations exist):
- A commodity-cycle shock hits revenue growth (iid per year) and EBIT margin (persistent AR(1)), correlated by `rho`.
- Capex intensity and tax-rate level shocks.
- Discount-rate inputs: risk-free, beta, equity risk premium. Terminal growth (triangular). GBP/USD (lognormal).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import numpy as np
import pandas as pd
from model.three_statement import Assumptions, BASE_YEAR, derive_base
from model.dcf import ValuationInputs, Bridge

import datetime as dt


@dataclass
class MCSpec:
    n: int = 10_000
    seed: int = 7
    sigma_growth: float = 0.05        # sd of annual revenue-growth shock
    sigma_margin: float = 0.016       # stationary sd of EBIT-margin shock (pp of revenue)
    rho: float = 0.6                  # correlation growth <-> margin innovations (commodity cycle)
    phi_margin: float = 0.75          # persistence of margin shocks
    sigma_capex: float = 0.004        # sd of capex-intensity level shock
    sigma_tax: float = 0.02           # sd of tax-rate level shock
    sigma_rf: float = 0.006
    sigma_beta: float = 0.12
    sigma_erp: float = 0.007
    g_low: float = 0.005
    g_high: float = 0.025
    sigma_fx: float = 0.07            # lognormal sd of GBP/USD at the horizon
    min_wacc_minus_g: float = 0.015


DRIVERS = ["growth", "margin", "capex", "tax", "risk_free", "beta", "erp", "terminal_growth", "fx"]
DRIVER_LABELS = {"growth": "Revenue growth", "margin": "EBIT margin", "capex": "Capex intensity",
                 "tax": "Tax rate", "risk_free": "Risk-free rate", "beta": "Beta", "erp": "Equity risk premium",
                 "terminal_growth": "Terminal growth", "fx": "GBP/USD"}


@dataclass
class Base:
    rev0: float
    growth: np.ndarray
    margin: np.ndarray
    tax: np.ndarray
    da_pct: np.ndarray
    capex_pct: np.ndarray
    lease_pct: np.ndarray
    nwc_pct: float
    rf: float
    beta: float
    erp: float
    g: float
    fx: float
    mcap: float
    debt: float
    credit_spread: float
    tax_shield: float
    shares_m: float
    dps: float
    net_claims: float            # everything deducted/added in the equity bridge, USD m (EV -> equity)
    years_roll: float


def make_base(h: pd.DataFrame, a: Assumptions, v: ValuationInputs, b: Bridge) -> Base:
    p = derive_base(h)
    bridge_adj = b.jv_investments - b.borrowings - b.leases + b.cash - b.nci
    if v.deduct_provisions:
        bridge_adj -= (b.provisions + b.pension_deficit) * (1 - v.tax_shield_rate)
    return Base(
        rev0=p["revenue"], growth=np.array(a.revenue_growth), margin=np.array(a.ebit_margin), tax=np.array(a.tax_rate),
        da_pct=np.array(a.da_pct), capex_pct=np.array(a.capex_pct), lease_pct=np.array(a.lease_pct),
        nwc_pct=a.receivable_pct + a.inventory_pct - a.payable_pct, rf=v.risk_free, beta=v.beta,
        erp=v.equity_risk_premium, g=v.terminal_growth, fx=b.fx_gbpusd, mcap=v.market_cap_usd_m,
        debt=v.debt_usd_m, credit_spread=v.credit_spread, tax_shield=v.tax_shield_rate, shares_m=b.shares_m,
        dps=b.dps_next_usd, net_claims=bridge_adj,
        years_roll=(v.valuation_date - dt.date(BASE_YEAR, 12, 31)).days / 365)


def _zeros(n: int, t: int) -> dict:
    return dict(growth=np.zeros((n, t)), margin=np.zeros((n, t)), capex=np.zeros(n), tax=np.zeros(n),
                risk_free=np.zeros(n), beta=np.zeros(n), erp=np.zeros(n), terminal_growth=np.zeros(n),
                fx=np.zeros(n))  # all shocks are additive except fx (log shock)


def draw(spec: MCSpec, base: Base) -> dict:
    rng = np.random.default_rng(spec.seed)
    n, t = spec.n, len(base.growth)
    z1 = rng.standard_normal((n, t))
    z2 = spec.rho * z1 + np.sqrt(1 - spec.rho ** 2) * rng.standard_normal((n, t))
    margin = np.zeros((n, t))
    innov_sd = spec.sigma_margin * np.sqrt(1 - spec.phi_margin ** 2)
    margin[:, 0] = spec.sigma_margin * z2[:, 0]
    for j in range(1, t):
        margin[:, j] = spec.phi_margin * margin[:, j - 1] + innov_sd * z2[:, j]
    d = _zeros(n, t)
    d["growth"] = spec.sigma_growth * z1
    d["margin"] = margin
    d["capex"] = spec.sigma_capex * rng.standard_normal(n)
    d["tax"] = spec.sigma_tax * rng.standard_normal(n)
    d["risk_free"] = spec.sigma_rf * rng.standard_normal(n)
    d["beta"] = spec.sigma_beta * rng.standard_normal(n)
    d["erp"] = spec.sigma_erp * rng.standard_normal(n)
    d["terminal_growth"] = rng.triangular(spec.g_low, base.g, spec.g_high, n) - base.g
    d["fx"] = spec.sigma_fx * rng.standard_normal(n) - 0.5 * spec.sigma_fx ** 2   # median-ish neutral
    return d


def evaluate(base: Base, d: dict, spec: MCSpec) -> dict:
    """Value per share in GBp for each path, plus the per-path intermediate drivers."""
    n, t = d["growth"].shape
    g = base.growth[None, :] + d["growth"]
    m = np.clip(base.margin[None, :] + d["margin"], 0.0, None)
    rev = base.rev0 * np.cumprod(1 + g, axis=1)
    prev = np.concatenate([np.full((n, 1), base.rev0), rev[:, :-1]], axis=1)
    tax = np.clip(base.tax[None, :] + d["tax"][:, None], 0.0, 0.7)
    capex_pct = np.clip(base.capex_pct[None, :] + d["capex"][:, None], 0.0, None)
    ebit = rev * m
    ufcf = ebit * (1 - tax) + rev * base.da_pct[None, :] - rev * capex_pct - rev * base.lease_pct[None, :] \
        - base.nwc_pct * (rev - prev)

    rf, beta, erp = base.rf + d["risk_free"], np.clip(base.beta + d["beta"], 0.3, None), np.clip(base.erp + d["erp"], 0.02, None)
    ke = rf + beta * erp
    kd = (rf + base.credit_spread) * (1 - base.tax_shield)
    wacc = (base.mcap * ke + base.debt * kd) / (base.mcap + base.debt)
    g_term = np.minimum(base.g + d["terminal_growth"], wacc - spec.min_wacc_minus_g)

    tt = np.arange(t) + 0.5
    pv = (ufcf / (1 + wacc[:, None]) ** tt[None, :]).sum(axis=1)
    tv = ufcf[:, -1] * (1 + g_term) / (wacc - g_term)
    ev = pv + tv / (1 + wacc) ** (t - 0.5)
    equity = ev + base.net_claims
    usd = equity / base.shares_m * (1 + ke) ** base.years_roll - base.dps * base.years_roll
    fx = base.fx * np.exp(d["fx"])
    pence = usd / fx * 100
    return dict(value=pence, ev=ev, wacc=wacc, g_term=g_term, ufcf=ufcf, ebitda_margin=m)


def base_path_value(base: Base, spec: MCSpec) -> float:
    t = len(base.growth)
    d = _zeros(1, t)
    return float(evaluate(base, d, spec)["value"][0])


def run(base: Base, spec: MCSpec) -> dict:
    d = draw(spec, base)
    res = evaluate(base, d, spec)
    v = res["value"]
    # rank correlation of each driver (summarised per path) with value
    summ = pd.DataFrame({
        "growth": d["growth"].mean(axis=1), "margin": d["margin"].mean(axis=1), "capex": d["capex"],
        "tax": d["tax"], "risk_free": d["risk_free"], "beta": d["beta"], "erp": d["erp"],
        "terminal_growth": d["terminal_growth"], "fx": d["fx"]})
    ranks = summ.rank().corrwith(pd.Series(v).rank())
    pct = {f"p{q}": float(np.percentile(v, q)) for q in (5, 10, 25, 50, 75, 90, 95)}
    return dict(values=v, draws=d, result=res, stats=dict(mean=float(v.mean()), std=float(v.std()), **pct),
                rank_corr=ranks.rename(index=DRIVER_LABELS), base_value=base_path_value(base, spec))


def tornado(base: Base, spec: MCSpec, draws: dict, q: float = 0.10) -> pd.DataFrame:
    """One-at-a-time sensitivity: each driver is moved to the P10 / P90 of its own simulated (path-average) shock,
    held constant across years, with every other driver at base. Returns value in GBp, sorted by swing."""
    t = len(base.growth)
    v0 = base_path_value(base, spec)
    rows = []
    for k in DRIVERS:
        x = draws[k]
        per_path = x.mean(axis=1) if x.ndim == 2 else x
        out = {}
        for tag, qq in (("low_shock", q), ("high_shock", 1 - q)):
            shock = float(np.quantile(per_path, qq))
            d = _zeros(1, t)
            d[k] = np.full((1, t), shock) if d[k].ndim == 2 else np.array([shock])
            out[tag] = float(evaluate(base, d, spec)["value"][0])
        rows.append(dict(driver=DRIVER_LABELS[k], p10_shock_value=out["low_shock"], p90_shock_value=out["high_shock"]))
    df = pd.DataFrame(rows)
    df["swing"] = (df.p10_shock_value - df.p90_shock_value).abs()
    df["base_value"] = v0
    return df.sort_values("swing", ascending=False).reset_index(drop=True)
