"""Shared glue: build valuation inputs / bridge for a company from history + market data."""
from __future__ import annotations
import json
import pandas as pd
from model.three_statement import BASE_YEAR, load_history, default_assumptions, forecast
from model.dcf import ValuationInputs, Bridge, build_bridge


def load_market() -> dict:
    return json.load(open("data/clean/market_inputs.json"))


def market_cap_usd(m: dict, fx: float) -> float:
    return m["shares_m"] * m["price_gbp_pence"] / 100 * fx


def valuation_inputs(h: pd.DataFrame, mk: dict, company: str, rf_mode: str = "blend", **over) -> ValuationInputs:
    c, m = mk["_common"], mk[company]
    rf = {"spot": c["risk_free_spot"], "blend": c["risk_free_blend"], "1y": c["risk_free_1y_avg"]}[rf_mode]
    debt_book = float(h.loc["debt_current", BASE_YEAR] + h.loc["debt_long", BASE_YEAR] + h.loc["lease_liabilities", BASE_YEAR])
    kw = dict(risk_free=rf, equity_risk_premium=c["equity_risk_premium"], beta=m["beta_blume"],
              market_cap_usd_m=market_cap_usd(m, c["gbpusd"]), debt_usd_m=debt_book)
    kw.update(over)
    return ValuationInputs(**kw)


def bridge_for(h: pd.DataFrame, mk: dict, company: str, a) -> Bridge:
    m, c = mk[company], mk["_common"]
    return build_bridge(h, m["shares_m"], c["gbpusd"], a.dividends[0] / m["shares_m"])
