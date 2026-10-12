import numpy as np
import pytest
from model.three_statement import load_history, default_assumptions, forecast
from model.dcf import dcf
from model.setup import load_market, valuation_inputs, bridge_for
from model.montecarlo import MCSpec, make_base, base_path_value, run, tornado, _zeros, evaluate


@pytest.fixture(scope="module", params=["shell", "bp"])
def ctx(request):
    c = request.param
    h, mk = load_history(c), load_market()
    a = default_assumptions(h)
    v, b = valuation_inputs(h, mk, c), bridge_for(h, mk, c, a)
    return dict(h=h, a=a, v=v, b=b, base=make_base(h, a, v, b), out=forecast(h, a))


def test_zero_shock_path_reproduces_dcf_exactly(ctx):
    spec = MCSpec()
    expected = dcf(ctx["out"], ctx["v"], ctx["b"])["value_per_share_gbp_pence"]
    assert base_path_value(ctx["base"], spec) == pytest.approx(expected, rel=1e-9)


def test_vectorised_ufcf_matches_forecast(ctx):
    d = _zeros(1, 10)
    res = evaluate(ctx["base"], d, MCSpec())
    assert np.allclose(res["ufcf"][0], ctx["out"]["kpis"].loc["unlevered_fcf"].values, rtol=1e-9)


def test_reproducible_with_seed(ctx):
    a = run(ctx["base"], MCSpec(n=2000, seed=3))["values"]
    b = run(ctx["base"], MCSpec(n=2000, seed=3))["values"]
    assert np.array_equal(a, b)


def test_percentiles_ordered_and_finite(ctx):
    r = run(ctx["base"], MCSpec(n=5000))
    s = r["stats"]
    assert np.isfinite(r["values"]).all()
    assert s["p5"] < s["p25"] < s["p50"] < s["p75"] < s["p95"]


def test_more_volatility_widens_distribution(ctx):
    lo = run(ctx["base"], MCSpec(n=5000, sigma_margin=0.005))["stats"]
    hi = run(ctx["base"], MCSpec(n=5000, sigma_margin=0.03))["stats"]
    assert (hi["p90"] - hi["p10"]) > (lo["p90"] - lo["p10"])


def test_margin_is_top_driver_by_rank_correlation(ctx):
    r = run(ctx["base"], MCSpec(n=8000))
    assert r["rank_corr"].abs().idxmax() in ("EBIT margin", "Revenue growth", "Equity risk premium", "Beta")
    assert r["rank_corr"]["EBIT margin"] > 0


def test_tornado_signs(ctx):
    spec = MCSpec(n=4000)
    r = run(ctx["base"], spec)
    t = tornado(ctx["base"], spec, r["draws"]).set_index("driver")
    assert t.loc["EBIT margin", "p90_shock_value"] > t.loc["EBIT margin", "p10_shock_value"]
    assert t.loc["Risk-free rate", "p90_shock_value"] < t.loc["Risk-free rate", "p10_shock_value"]
