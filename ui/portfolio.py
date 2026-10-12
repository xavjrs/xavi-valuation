"""Portfolio tab: 13-asset basket for a sterling investor."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model import portfolio as pm
from ui.theme import GOLD, GOLD_SOFT, IVORY, MUTED, WINE, SLATE, card, cards, style_fig, table_html

PALETTE = {"Max Sharpe": GOLD, "Min variance": "#8FA3B8", "Risk parity": "#B7C79A", "Max diversification": "#C98A97",
           "Equal weight": "#A0A4AE", "Custom": IVORY, pm.BENCH: "#6E6248"}


@st.cache_data(show_spinner=False)
def _data(assets: tuple, hedged: bool, years: int | None):
    px = pm.load_prices()
    pg = pm.gbp_prices(px, list(assets), hedged)
    if years:
        pg = pg[pg.index >= pg.index[-1] - pd.DateOffset(years=years)]
    return px, pg, pm.returns(pg, "W"), pm.returns(pg, "D")


@st.cache_data(show_spinner="Optimising portfolios…")
def _optimise(assets: tuple, hedged: bool, years, rf: float, erp: float, hw: float, cap: float):
    _, _, rw, _ = _data(assets, hedged, years)
    e = pm.estimate(rw, list(assets), rf, erp, hw)
    W = {name: f(e, cap) for name, f in pm.STRATEGIES.items()}
    return e, W, pm.frontier(e, cap, 30)


@st.cache_data(show_spinner="Running the walk-forward backtest…")
def _backtest(assets: tuple, hedged: bool, rf: float, erp: float, hw: float, cap: float, bps: float):
    _, _, rw, _ = _data(assets, hedged, None)          # backtest always uses the full history
    return pm.backtest(rw, list(assets), cap=cap, rf=rf, erp=erp, hist_weight=hw, cost_bps=bps)


@st.cache_data(show_spinner="Simulating future paths…")
def _simulate(w: tuple, assets: tuple, hedged: bool, years, rf, erp, hw, cap, horizon: int):
    e, _, _ = _optimise(assets, hedged, years, rf, erp, hw, cap)
    return pm.simulate(np.array(w), e, years=horizon)


def _p(x, d=1, sign=False):
    return f"{x*100:+.{d}f}%" if sign else f"{x*100:.{d}f}%"


def render() -> None:
    mk = json.load(open("data/clean/market_inputs.json"))
    st.markdown('<div class="section" style="margin-top:6px">Portfolio & risk</div>'
                '<div class="lede">The 13-asset basket seen by a sterling investor: nine UK shares, three US shares and an emerging-Asia ETF, '
                'with dollar assets converted to pounds. Weekly returns since January 2021 drive the estimates; expected returns blend history with a CAPM prior, '
                'because five years of history is a poor guide to the next five. Nothing here is a recommendation to buy or sell.</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1])
    chosen = c1.selectbox("Portfolio to analyse", list(pm.STRATEGIES) + ["Custom"], index=0, key="pf_sel")
    cap = c2.slider("Max weight per asset", 10, 100, 25, 5, key="pf_cap") / 100
    hw = c3.slider("Weight on history in expected returns", 0, 100, 25, 5, key="pf_hw",
                   help="0% = pure CAPM prior (risk-free + beta x ERP); 100% = trailing average return.") / 100
    hedged = c4.toggle("Hedge USD assets to GBP", value=False, key="pf_hedge")

    with st.expander("Universe, rates and backtest settings"):
        a1, a2, a3, a4 = st.columns(4)
        assets = a1.multiselect("Assets", list(pm.BASKET), default=list(pm.BASKET), key="pf_assets")
        rf = a2.slider("Risk-free rate", 0.0, 6.0, round(mk["_common"]["short_rate"] * 100, 2), 0.05, key="pf_rf",
                       help="Default: US 13-week T-bill. A sterling cash rate may differ.") / 100
        erp = a3.slider("Equity risk premium (prior)", 2.0, 8.0, 5.0, 0.25, key="pf_erp") / 100
        win = a4.radio("Estimation window", ["Full history", "Last 3 years"], horizontal=True, key="pf_win")
        b1, b2, _, _ = st.columns(4)
        bps = b1.slider("Trading cost (bp per unit of turnover)", 0, 50, 10, 5, key="pf_bps")
        horizon = b2.slider("Simulation horizon (years)", 1, 10, 5, 1, key="pf_hz")
    if len(assets) < 3:
        st.warning("Pick at least three assets.")
        return
    A = tuple(assets)
    years = 3 if win == "Last 3 years" else None
    px, pg, rw, rd = _data(A, hedged, years)
    e, W, fr = _optimise(A, hedged, years, rf, erp, hw, cap)

    if chosen == "Custom":
        with st.expander("Custom weights", expanded=True):
            cols = st.columns(4)
            raw = np.array([cols[i % 4].number_input(a, 0.0, 100.0, round(100 / len(A), 1), 1.0, key=f"pf_w_{a}") for i, a in enumerate(A)])
        W["Custom"] = raw / raw.sum() if raw.sum() > 0 else np.full(len(A), 1 / len(A))
    w = W[chosen]
    ws = pd.Series(w, index=list(A))
    s = pm.port_stats(w, e)
    real = pm.realised(ws, rd, pm.DAYS)
    vt = pm.var_table(real["series"])
    bets = pm.effective_bets(w, e.cov.values)

    st.markdown(cards([
        card("Expected return", _p(s["ret"]), f"blended estimate · risk-free {_p(rf, 2)}"),
        card("Volatility", _p(s["vol"]), f"Sharpe {s['sharpe']:.2f} · beta to FTSE 100 {s['beta']:.2f}"),
        card("1-day VaR (95%)", _p(vt.loc['95%', 'Historical VaR 1d'], 2), f"CVaR {_p(vt.loc['95%', 'Historical CVaR 1d'], 2)} · 99% VaR {_p(vt.loc['99%', 'Historical VaR 1d'], 2)}"),
        card("Diversification", f"{bets:.1f}", f"effective bets of {len(A)} · diversification ratio {s['div_ratio']:.2f}"),
    ]), unsafe_allow_html=True)
    st.markdown(cards([
        card("Realised return, since 2021", _p(real["ann_ret"], 1, True), "annualised, constant weights, history only"),
        card("Realised volatility", _p(real["ann_vol"]), "daily returns, annualised"),
        card("Maximum drawdown", _p(real["max_dd"]), "peak to trough, constant weights", tone="neg"),
        card("Covariance shrinkage", _p(e.shrinkage), f"Ledoit-Wolf · {e.n_obs} weekly observations"),
    ]), unsafe_allow_html=True)
    st.markdown('<div class="note"><b>Realised vs expected.</b> The realised figures apply today’s weights to the past, so they flatter any portfolio that was '
                'chosen with hindsight. The walk-forward backtest further down is the honest test.</div>', unsafe_allow_html=True)

    # ── frontier
    st.markdown('<div class="section">Efficient frontier</div><div class="lede">Every portfolio of these assets that gives the most expected return for its risk, '
                'subject to the weight cap. The line from the risk-free rate through the maximum-Sharpe portfolio is the capital market line.</div>', unsafe_allow_html=True)
    f = go.Figure()
    f.add_trace(go.Scatter(x=fr["vol"] * 100, y=fr["ret"] * 100, mode="lines", line=dict(color=GOLD, width=2), name="Efficient frontier",
                           hovertemplate="vol %{x:.1f}% · return %{y:.1f}%<extra></extra>"))
    sd = np.sqrt(np.diag(e.cov.values))
    f.add_trace(go.Scatter(x=sd * 100, y=e.mu.values * 100, mode="markers+text", text=list(A), textposition="top center", textfont=dict(size=10, color=MUTED),
                           marker=dict(size=8, color=SLATE, line=dict(color=IVORY, width=0.5)), name="Assets", hovertemplate="%{text}<br>vol %{x:.1f}% · return %{y:.1f}%<extra></extra>"))
    ms = pm.port_stats(W["Max Sharpe"], e)
    xs = np.linspace(0, max(fr["vol"].max(), ms["vol"]) * 1.15, 20)
    f.add_trace(go.Scatter(x=xs * 100, y=(rf + ms["sharpe"] * xs) * 100, mode="lines", line=dict(color=IVORY, width=1, dash="dot"), name="Capital market line", hoverinfo="skip"))
    for name, wv in W.items():
        st_ = pm.port_stats(wv, e)
        f.add_trace(go.Scatter(x=[st_["vol"] * 100], y=[st_["ret"] * 100], mode="markers", name=name,
                               marker=dict(size=14 if name == chosen else 11, symbol="diamond", color=PALETTE.get(name, IVORY), line=dict(color="#0A0A0C", width=1)),
                               hovertemplate=f"{name}<br>vol %{{x:.1f}}% · return %{{y:.1f}}%<extra></extra>"))
    style_fig(f, 460, legend=True)
    f.update_layout(xaxis_title="Volatility (% a year)", yaxis_title="Expected return (% a year)", margin=dict(l=18, r=18, t=60, b=40))
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

    # ── weights + risk contribution
    cL, cR = st.columns(2)
    with cL:
        wf = go.Figure()
        for name, wv in W.items():
            wf.add_trace(go.Bar(y=list(A), x=wv * 100, orientation="h", name=name, marker=dict(color=PALETTE.get(name, IVORY)),
                                hovertemplate=f"{name}: %{{x:.1f}}%<extra></extra>"))
        style_fig(wf, 520, legend=True)
        wf.update_layout(barmode="group", title="Weights by portfolio (%)", xaxis_title="Weight (%)", margin=dict(l=18, r=18, t=80, b=40), bargap=0.25)
        wf.update_yaxes(autorange="reversed")
        st.plotly_chart(wf, width="stretch", config={"displayModeBar": False})
    with cR:
        rc = pm.risk_contributions(w, e.cov.values)
        rcs = rc / rc.sum()
        rf_ = go.Figure()
        rf_.add_trace(go.Bar(y=list(A), x=w * 100, orientation="h", name="Weight", marker=dict(color=SLATE)))
        rf_.add_trace(go.Bar(y=list(A), x=rcs * 100, orientation="h", name="Share of risk", marker=dict(color=GOLD_SOFT, line=dict(color=GOLD, width=1))))
        style_fig(rf_, 520, legend=True)
        rf_.update_layout(barmode="group", title=f"{chosen}: capital vs risk (%)", xaxis_title="%", margin=dict(l=18, r=18, t=80, b=40), bargap=0.25)
        rf_.update_yaxes(autorange="reversed")
        st.plotly_chart(rf_, width="stretch", config={"displayModeBar": False})

    # ── correlations
    st.markdown('<div class="section">How the assets move together</div><div class="lede">Weekly return correlations in sterling. '
                'Lower numbers mean more diversification.</div>', unsafe_allow_html=True)
    corr = rw[list(A)].corr()
    order = corr.mean().sort_values(ascending=False).index
    corr = corr.loc[order, order]
    hm = go.Figure(go.Heatmap(z=corr.values, x=list(order), y=list(order), zmin=-0.2, zmax=1, text=[[f"{v:.2f}" for v in r] for r in corr.values],
                              texttemplate="%{text}", textfont=dict(size=10, color=IVORY), xgap=2, ygap=2, showscale=False,
                              colorscale=[[0, "#1B1B20"], [0.35, "#2A2620"], [0.7, "#6E6248"], [1, "#B8975A"]],
                              hovertemplate="%{y} / %{x}: %{text}<extra></extra>"))
    style_fig(hm, 520)
    hm.update_layout(margin=dict(l=150, r=18, t=18, b=120)); hm.update_yaxes(autorange="reversed")
    st.plotly_chart(hm, width="stretch", config={"displayModeBar": False})

    # ── currency
    fx = pm.fx_decomposition(px)
    fx = fx[fx.index.isin(A)]
    if len(fx):
        st.markdown('<div class="section">The currency leg</div>', unsafe_allow_html=True)
        fxt = fx.T
        st.markdown(table_html(fxt, {"vol_usd": "Volatility in dollars", "vol_gbp": "Volatility in pounds", "vol_fx": "GBP/USD volatility",
                                     "corr_asset_fx": "Correlation: asset vs dollar (in GBP)", "fx_share_of_variance": "Share of GBP variance added by FX"},
                               pct_rows={"vol_usd", "vol_gbp", "vol_fx", "fx_share_of_variance"}, row_digits={"corr_asset_fx": 2}), unsafe_allow_html=True)
        st.markdown('<div class="note"><b>Reading this.</b> A negative share means the currency <i>reduced</i> risk: these assets tend to fall in dollars when the dollar '
                    'strengthens against sterling, so the two legs partly offset. Hedging removes that cushion as well as the currency risk.</div>', unsafe_allow_html=True)

    # ── drawdown, VaR, stress
    st.markdown('<div class="section">Downside</div>', unsafe_allow_html=True)
    dL, dR = st.columns([1.3, 1])
    with dL:
        bench = (1 + rd[pm.BENCH]).cumprod()
        dd = go.Figure()
        dd.add_trace(go.Scatter(x=real["wealth"].index, y=real["wealth"], name=chosen, line=dict(color=GOLD, width=1.8)))
        dd.add_trace(go.Scatter(x=bench.index, y=bench, name="FTSE 100 ETF", line=dict(color=MUTED, width=1.2)))
        dd.add_trace(go.Scatter(x=real["drawdown"].index, y=real["drawdown"] * 100, name="Drawdown (%, right)", yaxis="y2", fill="tozeroy",
                                line=dict(color=WINE, width=0.8), fillcolor="rgba(155,74,90,.25)"))
        style_fig(dd, 380, legend=True)
        dd.update_layout(title="Growth of £1 and drawdown (today’s weights, in hindsight)", margin=dict(l=18, r=50, t=70, b=30),
                         yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(color=MUTED), range=[-60, 0]))
        st.plotly_chart(dd, width="stretch", config={"displayModeBar": False})
    with dR:
        st.markdown(table_html(vt.T, {}, pct_rows=set(vt.columns)), unsafe_allow_html=True)
        stt = pm.stress_tests(ws, e, rw, hedged)
        st.markdown(table_html(stt, {}, pct_rows={r_ for r_ in stt.index}), unsafe_allow_html=True)

    # ── backtest
    st.markdown('<div class="section">Walk-forward backtest</div><div class="lede">Every four weeks each strategy is re-estimated on the previous two years only and rebalanced, '
                f'paying {bps}bp per unit of turnover. No future data is used at any decision. The test period starts after the first two-year window.</div>', unsafe_allow_html=True)
    bt = _backtest(A, hedged, rf, erp, hw, cap, float(bps))
    bf = go.Figure()
    for c in bt["wealth"].columns:
        bf.add_trace(go.Scatter(x=bt["wealth"].index, y=bt["wealth"][c], name=c, line=dict(color=PALETTE.get(c, IVORY), width=2.2 if c == chosen else 1.3)))
    style_fig(bf, 400, legend=True)
    bf.update_layout(title=f"Growth of £1 from {bt['start']:%b %Y}", margin=dict(l=18, r=18, t=70, b=30))
    st.plotly_chart(bf, width="stretch", config={"displayModeBar": False})
    bst = bt["stats"].T
    st.markdown(table_html(bst, {"ann_return": "Annual return", "ann_vol": "Annual volatility", "sharpe": "Sharpe ratio", "max_drawdown": "Maximum drawdown",
                                 "avg_turnover": "Average turnover per rebalance"}, pct_rows={"ann_return", "ann_vol", "max_drawdown", "avg_turnover"},
                           row_digits={"sharpe": 2}), unsafe_allow_html=True)
    best = bt["stats"]["sharpe"].drop(pm.BENCH).idxmax()
    st.markdown(f'<div class="note"><b>What the backtest says.</b> Best risk-adjusted strategy over this window: <b>{best}</b>. '
                f'Optimised portfolios often fail to beat equal weighting out of sample because their return estimates are noisy. A short window '
                f'(about {len(bt["returns"]) // 52} years) that includes one market regime cannot separate skill from luck.</div>', unsafe_allow_html=True)

    # ── simulation
    st.markdown(f'<div class="section">The next {horizon} years</div><div class="lede">5,000 simulated monthly paths with fat tails (Student-t), using the estimated '
                'returns and covariance. Values are nominal pounds per £1 invested, before inflation, fees and tax.</div>', unsafe_allow_html=True)
    sim = _simulate(tuple(w), A, hedged, years, rf, erp, hw, cap, horizon)
    months = np.arange(1, horizon * 12 + 1) / 12
    fan = go.Figure()
    p = sim["pct"]
    fan.add_trace(go.Scatter(x=months, y=p[4], line=dict(width=0), hoverinfo="skip", showlegend=False))
    fan.add_trace(go.Scatter(x=months, y=p[0], fill="tonexty", fillcolor="rgba(201,169,97,.12)", line=dict(width=0), name="5th–95th percentile"))
    fan.add_trace(go.Scatter(x=months, y=p[3], line=dict(width=0), hoverinfo="skip", showlegend=False))
    fan.add_trace(go.Scatter(x=months, y=p[1], fill="tonexty", fillcolor="rgba(201,169,97,.25)", line=dict(width=0), name="25th–75th percentile"))
    fan.add_trace(go.Scatter(x=months, y=p[2], line=dict(color=GOLD, width=2), name="Median"))
    fan.add_trace(go.Scatter(x=months, y=(1 + rf) ** months, line=dict(color=IVORY, width=1, dash="dot"), name="Cash at risk-free"))
    style_fig(fan, 380, legend=True)
    fan.update_layout(xaxis_title="Years", yaxis_title="Value of £1", margin=dict(l=18, r=18, t=60, b=40))
    st.plotly_chart(fan, width="stretch", config={"displayModeBar": False})
    st.markdown(cards([
        card("Median outcome", f"£{sim['p50']:.2f}", f"for each £1 after {horizon} years"),
        card("Bad case · 5th percentile", f"£{sim['p5']:.2f}", "1 path in 20 ends lower"),
        card("Good case · 95th percentile", f"£{sim['p95']:.2f}", "1 path in 20 ends higher"),
        card("Chance of losing money", _p(sim["prob_loss"], 0), f"chance of trailing cash: {_p(sim['prob_below_cash'], 0)}"),
    ]), unsafe_allow_html=True)

    with st.expander("Method and limitations"):
        st.markdown(
            '<div class="note"><b>Data.</b> Adjusted closes (dividends reinvested) from Yahoo Finance; UK lines converted from pence, US lines converted at the daily GBP/USD rate. '
            'Benchmark: iShares Core FTSE 100 ETF (ISF.L). Holidays are forward-filled for up to five days.<br>'
            '<b>Estimates.</b> Covariance from weekly returns with Ledoit-Wolf shrinkage. Expected return = history weight × trailing mean + (1 − weight) × (risk-free + beta × ERP). '
            'Betas are measured against the FTSE 100 ETF, so US assets show low betas even though they carry global equity risk.<br>'
            '<b>Hedging.</b> “Hedged” uses local-currency returns and ignores the interest-rate carry of a real hedge.<br>'
            '<b>Limits.</b> Under six years of data, one rate cycle, no transaction taxes (UK stamp duty is 0.5% on purchases), no tax wrappers, and no liquidity limits. '
            'VaR at 10 days is scaled by the square root of time, which understates fat-tailed risk.</div>', unsafe_allow_html=True)
