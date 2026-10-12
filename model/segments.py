"""Shell segment financials (FY2023-FY2025) built from the 20-F segment note, for carve-out analysis.

EBITDA here is on a reported (IFRS) basis: total segment revenue (third-party + inter-segment) less purchases less
operating expenses. It excludes JV/associate profit, interest and other income (including divestment gains), and
impairments. The 'current cost of supplies' adjustment is reported separately and NOT added back (it is not cash).
Inter-segment sales are treated as if they would continue at arm's length after a separation.
"""
from __future__ import annotations
import pandas as pd

SEGMENTS = ["Integrated Gas", "Upstream", "Marketing", "Chemicals and Products", "Renewables and Energy Solutions"]
SHORT = {"Integrated Gas": "Integrated Gas", "Upstream": "Upstream", "Marketing": "Marketing",
         "Chemicals and Products": "Chemicals & Products", "Renewables and Energy Solutions": "Renewables & Energy Solutions"}


def load_segments() -> pd.DataFrame:
    return pd.read_csv("data/clean/shell_segments.csv")


def profile(segment: str, seg: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rows = metrics, columns = years (ascending)."""
    seg = load_segments() if seg is None else seg
    p = seg[seg.segment == segment].pivot(index="metric", columns="year", values="usd_m").sort_index(axis=1)
    out = pd.DataFrame(index=p.columns)
    out["revenue"] = p.loc["revenue_third_party"] + p.loc["revenue_inter_segment"]
    out["ebitda"] = out["revenue"] - p.loc["purchases"] - p.loc["opex"]
    out["da"] = p.loc["dda"] - p.loc["impairment_losses"] - p.loc["impairment_reversals"]  # reversals are negative
    out["ebit"] = out["ebitda"] - out["da"]
    out["capex"] = p.loc["capex"]
    out["impairments_net"] = p.loc["impairment_losses"] + p.loc["impairment_reversals"]
    out["jv_share"] = p.loc["jv_share"]
    out["ccs_adjustment"] = p.loc["ccs_adjustment_pre_tax"]
    out["adjusted_earnings"] = p.loc["adjusted_earnings"]
    out["income"] = p.loc["income"]
    out["ebitda_margin"] = out["ebitda"] / out["revenue"]
    out["da_pct"] = out["da"] / out["revenue"]
    out["capex_pct"] = out["capex"] / out["revenue"]
    out["cash_conversion"] = (out["ebitda"] - out["capex"]) / out["ebitda"]
    return out.T


def group_nwc_pct(h: pd.DataFrame, year: int = 2025) -> float:
    """Segment working capital is not disclosed; use the group ratio as a proxy."""
    return float((h.loc["receivables", year] + h.loc["inventories", year] - h.loc["payables", year]) / h.loc["revenue", year])
