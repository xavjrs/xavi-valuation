import numpy as np
import pandas as pd
import pytest
from model.portfolio import (BASKET, BENCH, load_prices, gbp_prices, returns, estimate, ledoit_wolf, port_stats,
                             risk_contributions, effective_bets, min_variance, max_sharpe, risk_parity, max_diversification,
                             equal_weight, frontier, STRATEGIES, backtest, simulate, var_table, stress_tests, fx_decomposition)

A = list(BASKET)
CAP = 0.25


@pytest.fixture(scope="module")
def data():
    px = load_prices()
    pg = gbp_prices(px, A)
    rw = returns(pg, "W")
    return dict(px=px, pg=pg, rw=rw, rd=returns(pg, "D"), e=estimate(rw, A))


def test_usd_assets_converted_to_gbp(data):
    px, pg = data["px"], data["pg"]
    d = pg.index[-1]
    assert pg.loc[d, "Coca-Cola"] == pytest.approx(px["Coca-Cola"].ffill().loc[d] / px["GBPUSD"].ffill().loc[d])
    assert pg.loc[d, "Barclays"] == pytest.approx(px["Barclays"].ffill().loc[d] / 100)


def test_hedged_view_uses_local_returns(data):
    ph = gbp_prices(data["px"], A, hedged=True)
    d = ph.index[-1]
    assert ph.loc[d, "Palantir"] == pytest.approx(data["px"]["Palantir"].ffill().loc[d])


def test_ledoit_wolf_is_psd_and_shrinks(data):
    cov, delta = ledoit_wolf(data["rw"][A])
    assert 0 <= delta <= 1
    assert np.linalg.eigvalsh(cov.values).min() > 0


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_weights_are_valid(data, name):
    w = STRATEGIES[name](data["e"], CAP)
    assert w.sum() == pytest.approx(1.0, abs=1e-8)
    assert (w >= -1e-10).all() and (w <= max(CAP, 1 / len(A)) + 1e-6).all()


def test_min_variance_has_lowest_volatility(data):
    e = data["e"]
    v_mv = port_stats(min_variance(e, CAP), e)["vol"]
    for name, f in STRATEGIES.items():
        assert v_mv <= port_stats(f(e, CAP), e)["vol"] + 1e-6, name


def test_max_sharpe_has_highest_sharpe(data):
    e = data["e"]
    s_ms = port_stats(max_sharpe(e, CAP), e)["sharpe"]
    for name, f in STRATEGIES.items():
        assert s_ms >= port_stats(f(e, CAP), e)["sharpe"] - 1e-6, name


def test_risk_contributions_sum_to_vol_and_parity_is_equal(data):
    e = data["e"]
    w = risk_parity(e, 1.0)
    rc = risk_contributions(w, e.cov.values)
    assert rc.sum() == pytest.approx(port_stats(w, e)["vol"])
    assert (rc / rc.sum()).std() < 0.01
    assert effective_bets(w, e.cov.values) == pytest.approx(len(A), rel=0.02)


def test_frontier_is_monotone(data):
    f = frontier(data["e"], CAP, 15)
    assert (np.diff(f["ret"]) >= -1e-8).all()
    assert (np.diff(f["vol"]) >= -1e-6).all()


def test_no_lookahead_in_backtest(data):
    rw = data["rw"]
    bt1 = backtest(rw, A, cap=CAP, strategies=["Min variance"])
    tampered = rw.copy()
    tampered.iloc[-20:, :] = tampered.iloc[-20:, :] * 5           # change only the last 20 weeks
    bt2 = backtest(tampered, A, cap=CAP, strategies=["Min variance"])
    w1, w2 = bt1["weights"]["Min variance"], bt2["weights"]["Min variance"]
    early = [d for d in w1.index if d < rw.index[-20]]
    assert np.allclose(w1.loc[early].values, w2.loc[early].values)


def test_var_ordering(data):
    w = pd.Series(equal_weight(data["e"]), index=A)
    t = var_table(data["rd"][A] @ w.values)
    assert t.loc["99%", "Historical VaR 1d"] > t.loc["95%", "Historical VaR 1d"] > 0
    assert (t["Historical CVaR 1d"] >= t["Historical VaR 1d"]).all()


def test_simulation_reproducible_and_ordered(data):
    w = equal_weight(data["e"])
    a, b = simulate(w, data["e"], n=1000), simulate(w, data["e"], n=1000)
    assert np.array_equal(a["terminal"], b["terminal"])
    assert a["p5"] < a["p50"] < a["p95"]


def test_stress_hedged_removes_fx_scenario(data):
    w = pd.Series(equal_weight(data["e"]), index=A)
    t = stress_tests(w, data["e"], data["rw"], hedged=True)
    assert t.loc["Sterling +10% against the dollar", "Portfolio return"] == 0.0


def test_fx_decomposition_covers_usd_assets(data):
    fx = fx_decomposition(data["px"])
    assert set(fx.index) == {a for a, (_, c) in BASKET.items() if c == "USD"}
    assert (fx["vol_gbp"] > 0).all()
