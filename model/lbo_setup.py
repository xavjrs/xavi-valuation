"""Default LBO inputs for a Shell division, calibrated from the segment history and market data."""
from __future__ import annotations
import numpy as np
import pandas as pd
from model.lbo import LBOInputs, run
from model.segments import profile, group_nwc_pct
from model.three_statement import load_history
from model.setup import load_market, market_cap_usd

GROWTH = [0.0, 0.01, 0.02, 0.02, 0.02, 0.02, 0.02]  # placeholder macro view, same as the group forecast


def shell_group_multiple() -> float:
    """Shell's own market-implied EV/EBITDA: (market cap + net debt incl. leases + minorities) / (operating EBIT + D&A)."""
    h, mk = load_history("shell"), load_market()
    ev = market_cap_usd(mk["shell"], mk["_common"]["gbpusd"]) + float(
        h.loc["debt_current", 2025] + h.loc["debt_long", 2025] + h.loc["lease_liabilities", 2025] - h.loc["cash", 2025] + h.loc["nci", 2025])
    ebitda = float(h.loc["ebit_ops", 2025] + h.loc["da_underlying", 2025])
    return ev / ebitda


def default_inputs(segment: str = "Marketing", scenario: str = "base", **over) -> LBOInputs:
    p = profile(segment)
    h, mk = load_history("shell"), load_market()
    m_ltm = float(p.loc["ebitda_margin", 2025])
    m_avg = float(p.loc["ebitda_margin"].mean())
    if scenario == "base":            # LTM margin persists, consistent with the price paid for LTM EBITDA
        margins = [m_ltm] * 7
    elif scenario == "downside":      # margin mean-reverts to the 3-year average less 0.5pp by year 3
        target = min(m_ltm, m_avg) - 0.005
        margins = [m_ltm + (target - m_ltm) * min(t / 3, 1.0) for t in range(1, 8)]
    else:                             # upside: +0.8pp
        margins = [m_ltm + 0.008] * 7
    g_shift = {"downside": -0.015, "base": 0.0, "upside": 0.01}[scenario]
    base = dict(
        revenue0=float(p.loc["revenue", 2025]), ltm_ebitda=float(p.loc["ebitda", 2025]),
        revenue_growth=[g + g_shift for g in GROWTH], ebitda_margin=margins,
        da_pct=float(p.loc["da_pct", 2025]), capex_pct=float(p.loc["capex_pct", 2025]), nwc_pct=group_nwc_pct(h),
        base_rate=float(mk["_common"]["short_rate"]),
        entry_multiple=round(shell_group_multiple() * 2) / 2,   # nearest 0.5x to Shell's own implied multiple
        label=scenario)
    base.update(over)
    return LBOInputs(**base)


if __name__ == "__main__":
    pd.options.display.float_format = "{:,.2f}".format
    print("Shell implied group EV/EBITDA: %.2fx" % shell_group_multiple())
    for seg in ("Marketing", "Chemicals and Products", "Integrated Gas", "Renewables and Energy Solutions"):
        p = profile(seg)
        print(f"\n=== {seg} ===")
        print(p.loc[["revenue", "ebitda", "ebitda_margin", "da", "capex", "cash_conversion"]].round(3).to_string())
        r = run(default_inputs(seg))
        ret = r["returns"]; fin = r["financeable"]
        print(f"entry {r['su']['ev']/1e3:,.1f}bn EV  equity {r['su']['equity']/1e3:,.1f}bn  IRR {ret["irr"]*100:.1f}% (financeable={fin})  MOIC {ret['moic']:.2f}x   flags: {r['flags']}")
