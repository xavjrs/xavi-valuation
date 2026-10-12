from dataclasses import replace
import numpy as np
import pytest
from model.pipeline import Settings
from model.ma import run_deal, DealInputs, breakeven_synergies, sensitivity_accretion, standalone
from model.three_statement import load_history, default_assumptions

S = Settings()
D = DealInputs()


@pytest.fixture(scope="module")
def base():
    return run_deal(S, D)


def test_opening_and_forecast_balance_sheets_balance(base):
    assert abs(base["opening_check"]) < 1e-6
    assert base["pf"]["balance_sheet"].loc["balance_check"].abs().max() < 1e-6


def test_sources_equal_uses(base):
    su = base["su"]
    assert sum(su["sources"].values()) == pytest.approx(sum(su["uses"].values()), rel=1e-9)


def test_goodwill_identity(base):
    p = base["ppa"]
    assert p["goodwill_created"] == pytest.approx(p["equity_purchase_price"] - p["fair_value_net_assets"])
    assert p["goodwill_total"] == pytest.approx(p["shell_goodwill_before"] + p["goodwill_created"] + p["divestment_adjustment"])
    assert p["fair_value_net_assets"] == pytest.approx(p["book_equity_parent"] + p["less_existing_goodwill"]
                                                       + p["plus_fair_value_writeup"] + p["less_deferred_tax"])


def test_ownership_split_matches_stock_consideration(base):
    su, v = base["su"], base["value"]
    new = D.pct_stock * (v["bp_market_cap"] * (1 + D.premium)) / base["prices"]["shell_usd"]
    assert su["new_shares_m"] == pytest.approx(new)
    assert su["ownership_bp"] == pytest.approx(new / (new + base["shares"]["shell"]))


def test_pro_forma_ebitda_is_sum_of_parts_plus_synergies():
    d = replace(D, synergies_runrate=0.0)
    r = run_deal(S, d)
    A, B = standalone(S)
    for y in r["years"]:
        expected = A["out"]["income_statement"].loc["ebitda", y] + B["out"]["income_statement"].loc["ebitda", y]
        assert r["pf"]["income_statement"].loc["ebitda", y] == pytest.approx(expected, rel=1e-9)


def test_synergy_phasing_in_year_one(base):
    assert base["accretion"].loc["synergies_pre_tax", base["years"][0]] == pytest.approx(D.synergies_runrate * D.synergy_phasing[0])


def test_higher_premium_lowers_accretion_and_value():
    lo = run_deal(S, replace(D, premium=0.10))
    hi = run_deal(S, replace(D, premium=0.50))
    y = lo["years"][1]
    assert lo["accretion"].loc["accretion", y] > hi["accretion"].loc["accretion", y]
    assert lo["value"]["intrinsic_accretion"] > hi["value"]["intrinsic_accretion"]


def test_more_synergies_raise_accretion_and_value():
    lo = run_deal(S, replace(D, synergies_runrate=0.0))
    hi = run_deal(S, replace(D, synergies_runrate=6_000.0))
    y = lo["years"][2]
    assert hi["accretion"].loc["accretion", y] > lo["accretion"].loc["accretion", y]
    assert hi["value"]["intrinsic_accretion"] > lo["value"]["intrinsic_accretion"]


def test_all_stock_deal_needs_little_debt():
    r = run_deal(S, replace(D, pct_stock=1.0))
    assert r["su"]["sources"]["Acquisition debt"] == pytest.approx(
        (r["su"]["uses"]["Advisory fees"]) / (1 - D.financing_fee_pct), rel=1e-6)
    assert r["su"]["ownership_bp"] > 0.3


def test_divestment_reduces_revenue_and_still_balances():
    r0 = run_deal(S, D)
    r1 = run_deal(S, replace(D, divest_pct_ebitda=0.10))
    assert r1["su"]["sources"]["Divestment proceeds"] > 0
    assert r1["pf"]["income_statement"].loc["revenue", r1["years"][0]] < r0["pf"]["income_statement"].loc["revenue", r0["years"][0]]
    assert abs(r1["opening_check"]) < 1e-6 and r1["pf"]["balance_sheet"].loc["balance_check"].abs().max() < 1e-6


def test_all_stock_deal_with_divestment_keeps_surplus_cash():
    # regression: proceeds larger than the cash the deal needs used to vanish from the opening balance sheet
    r = run_deal(S, replace(D, pct_stock=1.0, divest_pct_ebitda=0.10))
    su = r["su"]
    assert su["sources"]["Acquisition debt"] == 0.0
    assert su["uses"]["Surplus cash retained"] > 0
    assert sum(su["sources"].values()) == pytest.approx(sum(su["uses"].values()), rel=1e-9)
    assert abs(r["opening_check"]) < 1e-6 and r["pf"]["balance_sheet"].loc["balance_check"].abs().max() < 1e-6


def test_acquisition_debt_is_swept_down(base):
    ad = base["credit"].loc["acquisition_debt"].values
    assert ad[0] < base["su"]["sources"]["Acquisition debt"] and (np.diff(ad) <= 1e-6).all()


def test_breakeven_synergies_gives_zero_accretion():
    d = replace(D, premium=0.60, pct_stock=1.0)             # an all-stock deal at a rich premium is dilutive
    assert run_deal(S, replace(d, synergies_runrate=0.0))["accretion"].loc["accretion", 2029] < 0
    s_star = breakeven_synergies(S, d, year_index=2)
    assert np.isfinite(s_star) and s_star > 0
    r = run_deal(S, replace(d, synergies_runrate=s_star))
    assert r["accretion"].loc["accretion", r["years"][2]] == pytest.approx(0.0, abs=1e-4)


def test_sensitivity_grid_shape():
    g = sensitivity_accretion(S, D, [0.1, 0.3], [0.0, 0.5, 1.0], "premium", "pct_stock")
    assert g.shape == (2, 3)


def test_minorities_modelled_as_fixed_dollar_hybrid_coupons():
    A, B = standalone(S)
    assert B["a"].nci_income_fixed > 0
    # BP's profit to shareholders must not be wiped out by a proportional minority charge
    assert B["out"]["income_statement"].loc["net_income_parent", 2027] > 0.5 * B["out"]["income_statement"].loc["net_income", 2027]
