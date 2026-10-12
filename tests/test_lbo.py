from dataclasses import replace
import numpy as np
import pytest
import pandas as pd
from model.lbo import run, max_entry_multiple, sensitivity_irr, breakeven_margin_shock, sources_uses, N_PROJ
from model.lbo_setup import default_inputs
from model.segments import load_segments, profile, SEGMENTS


@pytest.fixture(scope="module")
def mk():
    i = default_inputs("Marketing")
    return i, run(i)


def test_sources_equal_uses(mk):
    i, r = mk
    su = r["su"]
    assert sum(su["sources"].values()) == pytest.approx(sum(su["uses"].values()))


def test_cash_and_debt_roll_forward(mk):
    i, r = mk
    p, su = r["projections"], r["su"]
    cash, tlb = su["min_cash"], su["sources"]["term_loan_b"]
    for t in range(1, N_PROJ + 1):
        c = p[t]
        assert c["cash"] == pytest.approx(cash + c["cfads"] - c["cash_interest"] - c["mandatory_amort"]
                                          + c["revolver_draw"] - c["revolver_repay"] - c["sweep"], abs=1e-4)
        assert c["term_loan_b"] == pytest.approx(tlb - c["mandatory_amort"] - c["sweep"], abs=1e-4)
        cash, tlb = c["cash"], c["term_loan_b"]
    assert (p.loc[["term_loan_b", "senior_notes", "mezzanine", "revolver"]] >= -1e-9).all().all()


def test_mezzanine_accretes_at_pik_rate(mk):
    i, r = mk
    p, su = r["projections"], r["su"]
    assert p.loc["mezzanine", 1] == pytest.approx(su["sources"]["mezzanine"] * (1 + i.mezz_pik))


def test_value_bridge_reconciles(mk):
    assert abs(mk[1]["returns"]["bridge_check"]) < 1e-6


def test_irr_matches_moic(mk):
    ret = mk[1]["returns"]
    assert (1 + ret["irr"]) ** ret["hold"] == pytest.approx(ret["moic"])


def test_higher_exit_multiple_raises_irr(mk):
    i, _ = mk
    lo = run(replace(i, exit_multiple=6.5))["returns"]["irr"]
    hi = run(replace(i, exit_multiple=8.5))["returns"]["irr"]
    assert hi > lo


def test_lower_entry_price_raises_irr(mk):
    i, _ = mk
    a = run(replace(i, entry_multiple=6.0, exit_multiple=7.5))["returns"]["irr"]
    b = run(replace(i, entry_multiple=8.0, exit_multiple=7.5))["returns"]["irr"]
    assert a > b


def test_max_entry_multiple_solves_target(mk):
    i, _ = mk
    target = 0.15
    m = max_entry_multiple(i, target)
    assert np.isfinite(m)
    assert run(replace(i, entry_multiple=m, exit_multiple=i.exit_mult))["returns"]["irr"] == pytest.approx(target, abs=1e-4)


def test_interest_cap_raises_tax(mk):
    i, _ = mk
    capped = run(i)["projections"].loc["tax", 1]
    uncapped = run(replace(i, interest_cap_pct_ebitda=None))["projections"].loc["tax", 1]
    assert capped >= uncapped


def test_sensitivity_grid_shape_and_monotone(mk):
    i, _ = mk
    g = sensitivity_irr(i, [6.0, 7.5, 9.0], [6.5, 7.5, 8.5])
    assert g.shape == (3, 3)
    assert (g.diff(axis=1).iloc[:, 1:] > 0).all().all()      # IRR rises with exit multiple
    assert (g.diff(axis=0).iloc[1:, :] < 0).all().all()      # and falls with entry multiple


def test_breakeven_margin_shock_is_consistent(mk):
    i, _ = mk
    s = breakeven_margin_shock(i, 0.0)
    j = replace(i, ebitda_margin=[m - s for m in i.ebitda_margin])
    assert run(j)["returns"]["irr"] == pytest.approx(0.0, abs=1e-3)


def test_unfinanceable_division_is_flagged():
    r = run(default_inputs("Chemicals and Products"))
    assert not r["financeable"]
    assert any("liquidity shortfall" in f for f in r["flags"])


def test_ltv_cap_limits_debt():
    i = replace(default_inputs("Marketing"), entry_multiple=3.0)
    su = sources_uses(i)
    assert su["debt"] <= i.max_ltv * su["ev"] + 1e-6 and su["equity"] > 0


def test_segment_data_ties_to_group_totals():
    seg = load_segments()
    for y in (2023, 2024, 2025):
        tot = seg[(seg.year == y) & (seg.segment == "Total")].set_index("metric").usd_m
        parts = seg[(seg.year == y) & (seg.segment != "Total")].groupby("metric").usd_m.sum()
        assert abs(parts["capex"] - tot["capex"]) <= 2 and abs(parts["dda"] - tot["dda"]) <= 2


def test_segment_profile_identities():
    for s in SEGMENTS:
        p = profile(s)
        assert (p.loc["ebit"] - (p.loc["ebitda"] - p.loc["da"])).abs().max() < 1e-6
