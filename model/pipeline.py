"""One call that runs forecast -> DCF -> scenarios -> sensitivity -> Monte Carlo for a company and set of settings."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from model.three_statement import (load_history, default_assumptions, forecast, hist_metrics, SCENARIOS, N_EXPLICIT)
from model.dcf import dcf, sensitivity, wacc
from model.setup import load_market, valuation_inputs, bridge_for
from model.montecarlo import MCSpec, make_base, run, tornado


@dataclass(frozen=True)
class Settings:
    company: str = "shell"
    scenario: str = "base"
    terminal_growth: float = 0.015
    equity_risk_premium: float = 0.05
    rf_mode: str = "blend"
    beta: float | None = None          # None -> market beta (Blume-adjusted)
    exit_multiple: float = 5.0
    impairment_allowance: float = 0.01
    margin_adj: float = 0.0            # pp added to every forecast year
    growth_adj: float = 0.0            # pp added to explicit years
    deduct_provisions: bool = True
    mc_n: int = 10_000
    mc_seed: int = 7
    sigma_growth: float = 0.05
    sigma_margin: float = 0.016
    rho: float = 0.6


def _assumptions(h, s: Settings, scenario: str):
    a = default_assumptions(h, scenario, terminal_growth=s.terminal_growth, impairment_allowance=s.impairment_allowance)
    a.ebit_margin = [m + s.margin_adj for m in a.ebit_margin]
    a.revenue_growth = [g + (s.growth_adj if i < N_EXPLICIT else 0.0) for i, g in enumerate(a.revenue_growth)]
    return a


def compute(s: Settings) -> dict:
    h, mk = load_history(s.company), load_market()
    m = mk[s.company]
    over = dict(equity_risk_premium=s.equity_risk_premium, terminal_growth=s.terminal_growth,
                exit_multiple=s.exit_multiple, deduct_provisions=s.deduct_provisions)
    if s.beta is not None:
        over["beta"] = s.beta
    v = valuation_inputs(h, mk, s.company, rf_mode=s.rf_mode, **over)

    a = _assumptions(h, s, s.scenario)
    out = forecast(h, a)
    b = bridge_for(h, mk, s.company, a)
    r = dcf(out, v, b)

    scen = {}
    for sc in SCENARIOS:
        a_sc = _assumptions(h, s, sc)
        o_sc = forecast(h, a_sc)
        r_sc = dcf(o_sc, v, bridge_for(h, mk, s.company, a_sc))
        scen[sc] = dict(gordon=r_sc["value_per_share_gbp_pence"], multiple=r_sc["multiple_method"]["value_per_share_gbp_pence"],
                        ev=r_sc["ev"], equity=r_sc["equity_value"])

    w0 = wacc(v)
    waccs = [w0 + d for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    growths = [s.terminal_growth + d for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    sens = sensitivity(out, v, b, waccs, growths)

    spec = MCSpec(n=s.mc_n, seed=s.mc_seed, sigma_growth=s.sigma_growth, sigma_margin=s.sigma_margin, rho=s.rho)
    base = make_base(h, a, v, b)
    mc = run(base, spec)
    tor = tornado(base, spec, mc["draws"])

    px = pd.read_csv("data/clean/prices.csv", index_col=0, parse_dates=True)["Shell" if s.company == "shell" else "BP"].dropna()
    yr = px.tail(252)

    return dict(h=h, hm=hist_metrics(h), a=a, out=out, v=v, b=b, r=r, scen=scen, sens=sens, spec=spec, mc=mc,
                tornado=tor, market=m, common=mk["_common"], price=m["price_gbp_pence"],
                range52=(float(yr.min()), float(yr.max())), wacc=w0)
