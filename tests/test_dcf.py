from dataclasses import replace
import pytest
from model.three_statement import load_history, default_assumptions, forecast
from model.dcf import dcf, wacc, sensitivity
from model.setup import load_market, valuation_inputs, bridge_for

COMPANIES = ["shell", "bp"]


@pytest.fixture(scope="module", params=COMPANIES)
def case(request):
    c = request.param
    h = load_history(c)
    mk = load_market()
    a = default_assumptions(h)
    return dict(h=h, a=a, out=forecast(h, a), v=valuation_inputs(h, mk, c), b=bridge_for(h, mk, c, a))


def test_value_falls_as_wacc_rises(case):
    lo = dcf(case["out"], replace(case["v"], wacc_override=0.07), case["b"])["value_per_share_gbp_pence"]
    hi = dcf(case["out"], replace(case["v"], wacc_override=0.10), case["b"])["value_per_share_gbp_pence"]
    assert lo > hi


def test_value_rises_with_terminal_growth(case):
    a = dcf(case["out"], replace(case["v"], terminal_growth=0.01), case["b"])["value_per_share_gbp_pence"]
    b = dcf(case["out"], replace(case["v"], terminal_growth=0.02), case["b"])["value_per_share_gbp_pence"]
    assert b > a


def test_wacc_between_cost_of_debt_and_equity(case):
    v = case["v"]
    assert (v.risk_free + v.credit_spread) * (1 - v.tax_shield_rate) < wacc(v) < v.risk_free + v.beta * v.equity_risk_premium


def test_rejects_wacc_below_growth(case):
    with pytest.raises(ValueError):
        dcf(case["out"], replace(case["v"], wacc_override=0.01), case["b"])


def test_ev_bridge_adds_up(case):
    r = dcf(case["out"], case["v"], case["b"])
    br = r["bridge"]
    assert br["equity_value"] == pytest.approx(sum(v for k, v in br.items() if k != "equity_value"))
    assert r["ev"] == pytest.approx(r["pv_flows"] + r["pv_terminal"])


def test_provision_toggle_lowers_value(case):
    on = dcf(case["out"], case["v"], case["b"])["equity_value"]
    off = dcf(case["out"], replace(case["v"], deduct_provisions=False), case["b"])["equity_value"]
    assert off > on


def test_sensitivity_centre_equals_point_estimate(case):
    w = wacc(case["v"])
    s = sensitivity(case["out"], case["v"], case["b"], [w], [case["v"].terminal_growth])
    assert s.iloc[0, 0] == pytest.approx(dcf(case["out"], case["v"], case["b"])["value_per_share_gbp_pence"])
