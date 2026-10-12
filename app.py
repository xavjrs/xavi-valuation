"""XAVI - corporate valuation suite. Run:  py -3.12 -m streamlit run app.py"""
from __future__ import annotations
import os
from pathlib import Path

os.chdir(Path(__file__).parent)  # data paths are relative to this folder

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from model.pipeline import Settings, compute
from model.three_statement import BASE_YEAR, SCENARIOS
from ui import buyout, deal, portfolio
from ui.theme import (CSS, LOGO_SVG, GOLD, GOLD_SOFT, IVORY, MUTED, WINE, SLATE, PANEL_HI, card, cards, fmt, style_fig, table_html)

st.set_page_config(page_title="XAVI · Valuation", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="expanded")
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

NAMES = {"shell": "Shell plc", "bp": "BP p.l.c."}


@st.cache_data(show_spinner="Running model and 10,000-path simulation…")
def cached_compute(s: Settings) -> dict:
    return compute(s)


# ───────────────────────────── sidebar ─────────────────────────────
with st.sidebar:
    st.markdown('<div class="sbtitle first">Company</div>', unsafe_allow_html=True)
    company = st.radio("Company", list(NAMES), format_func=NAMES.get, horizontal=True, label_visibility="collapsed")
    st.markdown('<div class="sbtitle">Scenario</div>', unsafe_allow_html=True)
    scenario = st.radio("Scenario", list(SCENARIOS), index=1, format_func=str.title, horizontal=True, label_visibility="collapsed")

    st.markdown('<div class="sbtitle">Operating view</div>', unsafe_allow_html=True)
    margin_adj = st.slider("EBIT margin adjustment (pp)", -4.0, 4.0, 0.0, 0.25) / 100
    growth_adj = st.slider("Revenue growth adjustment, yrs 1–5 (pp)", -4.0, 4.0, 0.0, 0.25) / 100
    imp = st.slider("Recurring impairment allowance (% rev.)", 0.0, 2.5, 1.0, 0.1) / 100

    st.markdown('<div class="sbtitle">Valuation</div>', unsafe_allow_html=True)
    tg = st.slider("Terminal growth", 0.0, 3.0, 1.5, 0.1) / 100
    erp = st.slider("Equity risk premium", 3.0, 8.0, 5.0, 0.25) / 100
    rf_mode = st.radio("Risk-free rate", ["blend", "spot", "1y"], horizontal=True,
                       format_func={"blend": "Blend", "spot": "Spot", "1y": "1y avg"}.get)
    exit_mult = st.slider("Exit EV/EBITDA (cross-check)", 3.0, 9.0, 5.0, 0.25)
    prov = st.toggle("Deduct provisions & pension deficit", value=True)

    with st.expander("Simulation"):
        mc_n = st.select_slider("Paths", [2_000, 5_000, 10_000, 25_000], value=10_000)
        sg = st.slider("Growth volatility (σ, pp/yr)", 1.0, 10.0, 5.0, 0.5) / 100
        sm = st.slider("Margin volatility (σ, pp)", 0.5, 4.0, 1.6, 0.1) / 100
        rho = st.slider("Growth–margin correlation", 0.0, 0.95, 0.6, 0.05)
        seed = st.number_input("Seed", 1, 9999, 7)

S = Settings(company=company, scenario=scenario, terminal_growth=tg, equity_risk_premium=erp, rf_mode=rf_mode,
             exit_multiple=exit_mult, impairment_allowance=imp, margin_adj=margin_adj, growth_adj=growth_adj,
             deduct_provisions=prov, mc_n=int(mc_n), mc_seed=int(seed), sigma_growth=sg, sigma_margin=sm, rho=rho)
R = cached_compute(S)
r, mc, out, price = R["r"], R["mc"], R["out"], R["price"]
val = r["value_per_share_gbp_pence"]
up = val / price - 1
p_above = float((mc["values"] > price).mean())
st_ = mc["stats"]

# ───────────────────────────── header ─────────────────────────────
st.markdown(
    f'<div class="brand"><div class="mark">{LOGO_SVG}</div><div class="tag">Corporate valuation suite</div>'
    f'<div class="asof">{NAMES[company]} · prices {R["market"]["price_date"]}</div></div>', unsafe_allow_html=True)

# Only the selected section is built on each run (st.tabs would rebuild all eight, about 40 charts, every time).
PAGES = ["Overview", "Financials", "Valuation", "Risk", "Buyout", "Deal", "Portfolio", "Method & data"]
page = st.radio("Section", PAGES, horizontal=True, key="nav", label_visibility="collapsed")

# ───────────────────────────── overview ─────────────────────────────
if page == "Overview":
    tone = "pos" if up >= 0 else "neg"
    st.markdown(cards([
        card("Intrinsic value · DCF", f"{val:,.0f}", f"{scenario.title()} case · perpetuity growth", "p"),
        card("Market price", f"{price:,.0f}", f"Close {R['market']['price_date']}", "p"),
        card("Implied upside", f"{up*100:+.1f}%", f"Cross-check, exit multiple: {r['multiple_method']['value_per_share_gbp_pence']:,.0f}p", tone=tone),
        card("Probability value > price", f"{p_above*100:.0f}%", f"{S.mc_n:,} simulated paths · median {st_['p50']:,.0f}p"),
    ]), unsafe_allow_html=True)

    st.markdown('<div class="section">Where the value sits</div><div class="lede">Each bar is a different lens on the same company. '
                'The dashed line is today’s share price; the gold diamond marks the selected case.</div>', unsafe_allow_html=True)

    # football field
    sens = R["sens"]
    core = sens.iloc[1:4, 1:4].values
    mm = r["multiple_method"]["value_per_share_gbp_pence"]
    fb = [
        ("52-week trading range", R["range52"][0], R["range52"][1], None),
        ("Scenarios · bear to bull (DCF)", R["scen"]["bear"]["gordon"], R["scen"]["bull"]["gordon"], R["scen"][scenario]["gordon"]),
        ("DCF · WACC ±0.5%, g ±0.5%", float(core.min()), float(core.max()), val),
        ("DCF · exit multiple ±1x", mm * 0 + R["scen"][scenario]["multiple"] - 0, R["scen"][scenario]["multiple"], mm),
        ("Monte Carlo · P10 to P90", st_["p10"], st_["p90"], st_["p50"]),
    ]
    # exit-multiple band recomputed from the multiple ±1x using the same engine
    from dataclasses import replace
    from model.dcf import dcf as _dcf
    lo_m = _dcf(out, replace(R["v"], exit_multiple=R["v"].exit_multiple - 1), R["b"])["multiple_method"]["value_per_share_gbp_pence"]
    hi_m = _dcf(out, replace(R["v"], exit_multiple=R["v"].exit_multiple + 1), R["b"])["multiple_method"]["value_per_share_gbp_pence"]
    fb[3] = ("DCF · exit multiple ±1x", lo_m, hi_m, mm)

    fig = go.Figure()
    labels = [f[0] for f in fb][::-1]
    for i, (name, lo, hi, mid) in enumerate(fb[::-1]):
        fig.add_trace(go.Bar(y=[name], x=[hi - lo], base=[lo], orientation="h", marker=dict(color=GOLD_SOFT, line=dict(color=GOLD, width=1)),
                             width=0.46, hovertemplate=f"{name}<br>{lo:,.0f}p – {hi:,.0f}p<extra></extra>", showlegend=False))
        fig.add_annotation(x=lo, y=name, text=f"{lo:,.0f}", showarrow=False, xanchor="right", xshift=-8, font=dict(size=11, color=MUTED))
        fig.add_annotation(x=hi, y=name, text=f"{hi:,.0f}", showarrow=False, xanchor="left", xshift=8, font=dict(size=11, color=MUTED))
        if mid is not None:
            fig.add_trace(go.Scatter(x=[mid], y=[name], mode="markers", marker=dict(symbol="diamond", size=11, color=IVORY,
                          line=dict(color=GOLD, width=1)), hovertemplate=f"{mid:,.0f}p<extra></extra>", showlegend=False))
    fig.add_vline(x=price, line=dict(color=IVORY, width=1, dash="dash"))
    fig.add_annotation(x=price, y=1.07, yref="paper", text=f"Market {price:,.0f}p", showarrow=False, font=dict(size=11, color=IVORY))
    style_fig(fig, 360)
    fig.update_layout(xaxis_title="Value per share (pence)", barmode="overlay", margin=dict(l=18, r=40, t=40, b=40))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.markdown('<div class="section" style="margin-top:18px">From enterprise to equity</div>', unsafe_allow_html=True)
        br = r["bridge"]
        order = [("enterprise_value", "Enterprise value"), ("jv_investments", "JV & associates"), ("borrowings", "Borrowings"),
                 ("leases", "Leases"), ("cash", "Cash"), ("minorities", "Minorities"),
                 ("provisions_after_tax", "Provisions"), ("pension_deficit_after_tax", "Pension deficit")]
        order = [(k, l) for k, l in order if k in br]
        wf = go.Figure(go.Waterfall(
            x=[l for _, l in order] + ["Equity value"], measure=["absolute"] + ["relative"] * (len(order) - 1) + ["total"],
            y=[br[k] / 1e3 for k, _ in order] + [0], connector=dict(line=dict(color="rgba(237,230,214,.25)", width=1)),
            increasing=dict(marker=dict(color=GOLD)), decreasing=dict(marker=dict(color=WINE)), totals=dict(marker=dict(color=IVORY)),
            text=[f"{br[k]/1e3:,.1f}" for k, _ in order] + [f"{br['equity_value']/1e3:,.1f}"], textposition="outside",
            textfont=dict(size=11, color=IVORY), hovertemplate="%{x}: $%{y:,.1f}bn<extra></extra>"))
        style_fig(wf, 380)
        wf.update_layout(yaxis_title="USD bn", margin=dict(l=18, r=18, t=18, b=30))
        st.plotly_chart(wf, width="stretch", config={"displayModeBar": False})
    with c2:
        st.markdown('<div class="section" style="margin-top:18px">Three cases</div>', unsafe_allow_html=True)
        trio = []
        for sc in SCENARIOS:
            v_ = R["scen"][sc]["gordon"]
            trio.append(f'<div class="card {"on" if sc == scenario else ""}"><div class="k">{sc}</div>'
                        f'<div class="v">{v_:,.0f}<small>p</small></div><div class="s">{(v_/price-1)*100:+.0f}% vs market · EV ${R["scen"][sc]["ev"]/1e3:,.0f}bn</div></div>')
        st.markdown(cards(trio, "tri"), unsafe_allow_html=True)
        st.markdown(
            f'<div class="note"><b>Reading this.</b> WACC is {R["wacc"]*100:.2f}% (cost of equity {r["cost_of_equity"]*100:.2f}%), '
            f'terminal growth {tg*100:.1f}%. Terminal value is {r["tv_share_of_ev"]*100:.0f}% of enterprise value and implies '
            f'{r["implied_exit_ev_ebitda"]:.1f}x EBITDA. Results are driven by the assumptions in the sidebar, not by a view on the stock.</div>',
            unsafe_allow_html=True)

# ───────────────────────────── financials ─────────────────────────────
if page == "Financials":
    h, hm = R["h"], R["hm"]
    st.markdown('<div class="section" style="margin-top:6px">Reported history</div><div class="lede">Annual IFRS figures from SEC Form 20-F filings, USD millions. '
                'Operating EBIT excludes associates/JVs and non-operating finance items; impairments are shown separately.</div>', unsafe_allow_html=True)
    hist_rows = ["revenue", "ebit_ops", "impairment_net", "jv_share", "net_income", "cfo", "capex", "lease_principal", "cash", "equity_investments"]
    hist = h.loc[hist_rows].copy()
    hist.loc["fcf"] = h.loc["cfo"] - h.loc["capex"] - h.loc["lease_principal"]
    hist.loc["net_debt"] = h.loc["debt_current"] + h.loc["debt_long"] + h.loc["lease_liabilities"] - h.loc["cash"]
    hist.columns = [str(c) for c in hist.columns]
    hl = {"revenue": "Revenue", "ebit_ops": "Operating EBIT", "impairment_net": "Net impairments (in EBIT)", "jv_share": "Share of JV/associate profit",
          "net_income": "Net income", "cfo": "Cash from operations", "capex": "Capital expenditure", "lease_principal": "Lease principal repaid",
          "cash": "Cash", "equity_investments": "Equity-method investments", "fcf": "Free cash flow after leases", "net_debt": "Net debt incl. leases"}
    st.markdown(table_html(hist, hl, totals={"revenue", "net_income", "fcf"}), unsafe_allow_html=True)

    cm = go.Figure()
    years = [BASE_YEAR - 4 + i for i in range(5)] + list(out["income_statement"].columns)
    rev_all = list(h.loc["revenue"].values) + list(out["income_statement"].loc["revenue"].values)
    mar_all = list(hm.loc["ebit_margin_ex_impairment"].values) + list(out["income_statement"].loc["ebit"] / out["income_statement"].loc["revenue"])
    cm = make_subplots(specs=[[{"secondary_y": True}]])
    cm.add_trace(go.Bar(x=years, y=[x / 1e3 for x in rev_all], name="Revenue (USD bn)",
                        marker=dict(color=[SLATE] * 5 + [GOLD_SOFT] * len(out["income_statement"].columns), line=dict(width=0))), secondary_y=False)
    cm.add_trace(go.Scatter(x=years, y=[m * 100 for m in mar_all], name="Operating margin ex-impairment (%)", mode="lines+markers",
                            line=dict(color=IVORY, width=1.6), marker=dict(size=6)), secondary_y=True)
    cm.add_vline(x=BASE_YEAR + 0.5, line=dict(color=MUTED, width=1, dash="dot"))
    style_fig(cm, 340, legend=True)
    cm.update_yaxes(title_text="USD bn", secondary_y=False); cm.update_yaxes(title_text="%", secondary_y=True, showgrid=False)
    st.plotly_chart(cm, width="stretch", config={"displayModeBar": False})

    sub = st.tabs(["Income statement", "Balance sheet", "Cash flow", "Key metrics"])
    IS, BS, CF, KP = out["income_statement"], out["balance_sheet"], out["cash_flow"], out["kpis"]
    show = lambda df: df.rename(columns=lambda c: f"{c}E")
    with sub[0]:
        st.markdown(table_html(show(IS), {"revenue": "Revenue", "ebitda": "EBITDA", "da": "Depreciation & amortisation", "ebit": "Operating EBIT",
            "interest_expense": "Interest expense", "interest_income": "Interest income", "pbt_ex_jv": "Pre-tax profit (ex-JV)", "tax": "Tax",
            "jv_income": "Share of JV/associate profit", "net_income": "Net income", "net_income_minorities": "Minorities",
            "net_income_parent": "Net income to shareholders"}, totals={"revenue", "ebit", "net_income", "net_income_parent"}), unsafe_allow_html=True)
    with sub[1]:
        st.markdown(table_html(show(BS), {"cash": "Cash", "receivables": "Receivables", "inventories": "Inventories", "fixed_assets": "Fixed assets incl. right-of-use",
            "goodwill": "Goodwill", "other_assets": "Other assets (incl. JV stakes)", "total_assets": "Total assets", "payables": "Payables",
            "borrowings": "Borrowings", "revolver": "Revolver", "leases": "Lease liabilities", "other_liabilities": "Other liabilities (incl. provisions)",
            "total_liabilities": "Total liabilities", "equity_parent": "Shareholders’ equity", "minorities": "Minorities", "total_equity": "Total equity",
            "balance_check": "Balance check (should be 0)"}, totals={"total_assets", "total_liabilities", "total_equity"}, digits=0), unsafe_allow_html=True)
        st.markdown(f'<span class="pill ok">Balance sheet balances</span> max abs difference {BS.loc["balance_check"].abs().max():.1e}', unsafe_allow_html=True)
    with sub[2]:
        st.markdown(table_html(show(CF), {"net_income": "Net income", "da": "Depreciation & amortisation", "change_in_nwc": "Change in working capital",
            "cfo": "Cash from operations", "capex": "Capital expenditure", "cfi": "Cash from investing", "net_debt_issuance": "Net debt issued",
            "revolver_draw_repay": "Revolver draw / (repay)", "dividends": "Dividends", "buybacks": "Share buybacks", "minority_distributions": "Minority distributions",
            "lease_principal": "Lease principal", "cff": "Cash from financing", "net_change_in_cash": "Net change in cash", "closing_cash": "Closing cash"},
            totals={"cfo", "cfi", "cff", "closing_cash"}), unsafe_allow_html=True)
    with sub[3]:
        k = KP.copy()
        st.markdown(table_html(show(k), {"revenue_growth": "Revenue growth", "ebit_margin": "Operating margin", "free_cash_flow": "Free cash flow after leases",
            "unlevered_fcf": "Unlevered free cash flow", "net_debt": "Net debt incl. leases", "net_debt_to_ebitda": "Net debt / EBITDA"},
            totals={"unlevered_fcf"}, pct_rows={"revenue_growth", "ebit_margin"}, mult_rows={"net_debt_to_ebitda"}), unsafe_allow_html=True)

# ───────────────────────────── valuation ─────────────────────────────
if page == "Valuation":
    v = R["v"]
    st.markdown('<div class="section" style="margin-top:6px">Cost of capital</div>', unsafe_allow_html=True)
    e, d = v.market_cap_usd_m, v.debt_usd_m
    st.markdown(cards([
        card("Risk-free", f"{v.risk_free*100:.2f}%", f"US 10y · spot {R['common']['risk_free_spot']*100:.2f}%, 1y avg {R['common']['risk_free_1y_avg']*100:.2f}%"),
        card("Cost of equity", f"{r['cost_of_equity']*100:.2f}%", f"β {v.beta:.2f} × ERP {v.equity_risk_premium*100:.1f}%"),
        card("After-tax cost of debt", f"{((v.risk_free+v.credit_spread)*(1-v.tax_shield_rate))*100:.2f}%", f"spread {v.credit_spread*1e4:.0f}bp, shield {v.tax_shield_rate*100:.0f}%"),
        card("WACC", f"{R['wacc']*100:.2f}%", f"Equity {e/(e+d)*100:.0f}% · debt & leases {d/(e+d)*100:.0f}%"),
    ]), unsafe_allow_html=True)

    st.markdown('<div class="section">Sensitivity</div><div class="lede">Value per share in pence across discount rate and terminal growth. '
                'Cells are shaded relative to today’s price — gold above, wine below.</div>', unsafe_allow_html=True)
    sens = R["sens"]
    z = sens.values
    dev = np.clip((z / price - 1), -0.7, 0.7)
    hm_fig = go.Figure(go.Heatmap(z=dev, x=list(sens.columns), y=list(sens.index), text=[[f"{x:,.0f}" for x in row] for row in z],
                                  texttemplate="%{text}", textfont=dict(size=13, color=IVORY), showscale=False, xgap=3, ygap=3,
                                  colorscale=[[0, "#6E2F3C"], [0.42, "#2A1A20"], [0.5, "#1B1B20"], [0.58, "#3A3220"], [1, "#B8975A"]], zmid=0,
                                  hovertemplate="WACC %{y} · %{x}<br>%{text}p<extra></extra>"))
    style_fig(hm_fig, 330)
    hm_fig.update_layout(margin=dict(l=70, r=18, t=18, b=40)); hm_fig.update_yaxes(type="category", autorange="reversed", title_text="WACC"); hm_fig.update_xaxes(type="category")
    st.plotly_chart(hm_fig, width="stretch", config={"displayModeBar": False})

    cA, cB = st.columns(2)
    mm = r["multiple_method"]
    with cA:
        st.markdown('<div class="section" style="margin-top:12px">Perpetuity growth</div>', unsafe_allow_html=True)
        st.markdown(cards([card("PV of 10-year cash flows", f"${r['pv_flows']/1e3:,.0f}", "billion", ), card("PV of terminal value", f"${r['pv_terminal']/1e3:,.0f}", f"{r['tv_share_of_ev']*100:.0f}% of EV · implies {r['implied_exit_ev_ebitda']:.1f}x EBITDA")],
                          "tri", "grid-template-columns:1fr 1fr"), unsafe_allow_html=True)
    with cB:
        st.markdown('<div class="section" style="margin-top:12px">Exit multiple cross-check</div>', unsafe_allow_html=True)
        st.markdown(cards([card("Value per share", f"{mm['value_per_share_gbp_pence']:,.0f}", f"at {mm['exit_multiple']:.1f}x EBITDA", "p"),
                           card("Implied perpetual growth", f"{mm['implied_perpetual_growth']*100:.1f}%", "what the multiple assumes")],
                          "tri", "grid-template-columns:1fr 1fr"), unsafe_allow_html=True)

    fcf = out["kpis"].loc[["unlevered_fcf"]].T
    fc = go.Figure(go.Bar(x=[f"{c}E" for c in fcf.index], y=fcf["unlevered_fcf"] / 1e3, marker=dict(color=GOLD_SOFT, line=dict(color=GOLD, width=1)),
                          hovertemplate="%{x}: $%{y:,.1f}bn<extra></extra>"))
    style_fig(fc, 280); fc.update_layout(title="Unlevered free cash flow (USD bn)", margin=dict(l=18, r=18, t=46, b=28))
    st.plotly_chart(fc, width="stretch", config={"displayModeBar": False})

# ───────────────────────────── risk ─────────────────────────────
if page == "Risk":
    vals = mc["values"]
    st.markdown(cards([
        card("Median", f"{st_['p50']:,.0f}", f"Mean {st_['mean']:,.0f}p · σ {st_['std']:,.0f}p", "p"),
        card("Likely range · P10–P90", f"{st_['p10']:,.0f}–{st_['p90']:,.0f}", "80% of simulated outcomes", "p"),
        card("Tail · P5 / P95", f"{st_['p5']:,.0f} / {st_['p95']:,.0f}", "pence per share"),
        card("P(value > market)", f"{p_above*100:.0f}%", f"Market {price:,.0f}p", tone="pos" if p_above >= .5 else "neg"),
    ]), unsafe_allow_html=True)

    lo_, hi_ = np.percentile(vals, [0.5, 99.5])
    counts, edges = np.histogram(vals[(vals >= lo_) & (vals <= hi_)], bins=64)
    mids = (edges[:-1] + edges[1:]) / 2
    hist_fig = go.Figure()
    hist_fig.add_trace(go.Bar(x=mids[mids < price], y=counts[mids < price] / len(vals) * 100, marker=dict(color="rgba(155,74,90,.75)"), name="Below market",
                              hovertemplate="%{x:,.0f}p · %{y:.2f}%<extra></extra>"))
    hist_fig.add_trace(go.Bar(x=mids[mids >= price], y=counts[mids >= price] / len(vals) * 100, marker=dict(color="rgba(201,169,97,.8)"), name="Above market",
                              hovertemplate="%{x:,.0f}p · %{y:.2f}%<extra></extra>"))
    for q, nm in (("p10", "P10"), ("p50", "Median"), ("p90", "P90")):
        hist_fig.add_vline(x=st_[q], line=dict(color=IVORY, width=1, dash="dot"), annotation_text=nm, annotation_font=dict(size=10, color=MUTED), annotation_position="top")
    hist_fig.add_vline(x=price, line=dict(color=IVORY, width=1.4), annotation_text=f"Market {price:,.0f}p", annotation_font=dict(size=11, color=IVORY), annotation_position="top right")
    style_fig(hist_fig, 380, legend=True)
    hist_fig.update_layout(title="Distribution of intrinsic value per share", bargap=0.04, xaxis_title="Pence per share", yaxis_title="% of paths", margin=dict(l=18, r=18, t=60, b=70),
                           legend=dict(orientation="h", x=1, xanchor="right", y=-0.22, font=dict(size=11, color=MUTED)))
    st.plotly_chart(hist_fig, width="stretch", config={"displayModeBar": False})

    cL, cR = st.columns(2)
    with cL:
        t = R["tornado"].iloc[::-1]
        tor = go.Figure()
        base_v = float(t["base_value"].iloc[0])
        tor.add_trace(go.Bar(y=t["driver"], x=t["p10_shock_value"] - base_v, base=base_v, orientation="h", name="Driver at P10 shock",
                             marker=dict(color="rgba(155,74,90,.8)"), hovertemplate="%{y} · P10 shock: %{customdata:,.0f}p<extra></extra>", customdata=t["p10_shock_value"]))
        tor.add_trace(go.Bar(y=t["driver"], x=t["p90_shock_value"] - base_v, base=base_v, orientation="h", name="Driver at P90 shock",
                             marker=dict(color="rgba(201,169,97,.8)"), hovertemplate="%{y} · P90 shock: %{customdata:,.0f}p<extra></extra>", customdata=t["p90_shock_value"]))
        tor.add_vline(x=base_v, line=dict(color=IVORY, width=1))
        style_fig(tor, 390, legend=True)
        tor.update_layout(title="What moves the value · tornado", barmode="overlay", xaxis_title="Pence per share", margin=dict(l=18, r=18, t=70, b=40))
        st.plotly_chart(tor, width="stretch", config={"displayModeBar": False})
    with cR:
        u = mc["result"]["ufcf"] / 1e3
        qs = np.percentile(u, [10, 50, 90], axis=0)
        yrs = [f"{c}E" for c in out["kpis"].columns]
        fan = go.Figure()
        fan.add_trace(go.Scatter(x=yrs, y=qs[2], line=dict(width=0), hoverinfo="skip", showlegend=False))
        fan.add_trace(go.Scatter(x=yrs, y=qs[0], fill="tonexty", fillcolor="rgba(201,169,97,.16)", line=dict(width=0), name="P10–P90", hoverinfo="skip"))
        fan.add_trace(go.Scatter(x=yrs, y=qs[1], line=dict(color=GOLD, width=2), name="Median", hovertemplate="%{x}: $%{y:,.1f}bn<extra></extra>"))
        fan.add_trace(go.Scatter(x=yrs, y=out["kpis"].loc["unlevered_fcf"] / 1e3, line=dict(color=IVORY, width=1.2, dash="dot"), name="Selected case"))
        style_fig(fan, 390, legend=True)
        fan.update_layout(title="Unlevered free cash flow · simulated range (USD bn)", margin=dict(l=18, r=18, t=70, b=40))
        st.plotly_chart(fan, width="stretch", config={"displayModeBar": False})

    with st.expander("Simulation design and caveats"):
        sp = R["spec"]
        st.markdown(
            f"""<div class="note"><b>Drivers.</b> A commodity-cycle shock moves revenue growth (iid, σ {sp.sigma_growth*100:.1f}pp/yr) and operating margin (AR(1), persistence {sp.phi_margin}, σ {sp.sigma_margin*100:.1f}pp),
            correlated at {sp.rho}. Capex intensity (σ {sp.sigma_capex*100:.1f}pp) and tax rate (σ {sp.sigma_tax*100:.0f}pp) shift by level. Discount rate: risk-free σ {sp.sigma_rf*100:.1f}pp, beta σ {sp.sigma_beta}, ERP σ {sp.sigma_erp*100:.1f}pp.
            Terminal growth is triangular {sp.g_low*100:.1f}% / {R['v'].terminal_growth*100:.1f}% / {sp.g_high*100:.1f}%; GBP/USD lognormal σ {sp.sigma_fx*100:.0f}%.<br>
            <b>Caveat.</b> Only five annual observations exist, so the volatilities are judgement, not estimates. Oil and gas prices are not modelled explicitly; the cycle factor stands in for them. Treat the shape of the distribution as more informative than any single percentile.</div>""",
            unsafe_allow_html=True)

# ───────────────────────────── buyout ─────────────────────────────
if page == "Buyout":
    buyout.render(company)

# ───────────────────────────── deal ─────────────────────────────
if page == "Deal":
    deal.render(S)

# ───────────────────────────── portfolio ─────────────────────────────
if page == "Portfolio":
    portfolio.render()

# ───────────────────────────── method ─────────────────────────────
if page == "Method & data":
    st.markdown('<div class="section" style="margin-top:6px">Method & data</div>', unsafe_allow_html=True)
    st.markdown(
        f"""<div class="note"><b>Financials.</b> SEC Form 20-F XBRL (IFRS), FY2021–FY2025, USD. Every extracted year satisfies assets = liabilities + equity and pre-tax profit − tax = net income.<br>
        <b>Forecast.</b> Ten years: five explicit, five fading to terminal growth. Operating EBIT excludes JV profit (valued at book in the bridge). Leases are debt. Buybacks flex to protect a cash floor; a revolver is drawn if needed.<br>
        <b>Valuation.</b> Unlevered DCF, mid-year convention, struck at 31 Dec {BASE_YEAR} and rolled forward at the cost of equity. Bridge deducts borrowings, leases, minorities, after-tax decommissioning/other provisions and any pension deficit; adds JV stakes.<br>
        <b>Buyout.</b> Divisional financials from the segment note of Shell’s FY2025 Form 20-F (validated to the group accounts). Carve-out LBO with term loan B, senior notes, PIK mezzanine, cash sweep and a standalone-cost drag; see the assumptions panel on the Buyout tab.<br>
        <b>Deal.</b> Shell acquires BP: purchase accounting (IFRS 3), a pro forma balance sheet, and the enlarged group forecast with the same engine; EPS accretion and a DCF-based value test. Hybrid bonds are modelled as fixed minority coupons.<br>
        <b>Market data.</b> Prices, beta (5y weekly vs FTSE 100, Blume-adjusted) and the US 10-year yield from Yahoo Finance via yfinance; unofficial, so spot-check before relying on it. Share count cross-checked to the 20-F for Shell.</div>""",
        unsafe_allow_html=True)
    st.markdown('<div class="section">Components</div>', unsafe_allow_html=True)
    st.markdown('<span class="pill ok">3-statement</span><span class="pill ok">DCF</span><span class="pill ok">Monte Carlo</span>'
                '<span class="pill ok">LBO · carve-out</span><span class="pill ok">M&A · Shell + BP</span><span class="pill ok">Portfolio & quant</span>'
                '<span class="pill ok">Excel export</span><span class="pill ok">Audit</span>', unsafe_allow_html=True)

    st.markdown('<div class="section">Audit</div><div class="lede">Integrity checks across the data, every model and the Excel workbook, '
                'from <code>audit.py</code>. Re-run it after refreshing data or changing code. The full assumptions log and methodology are in '
                '<code>docs/ASSUMPTIONS.md</code> and <code>docs/METHODOLOGY.md</code>.</div>', unsafe_allow_html=True)
    try:
        import json as _json
        aud = _json.load(open("output/audit.json"))
        df_a = pd.DataFrame(aud["results"])
        ok_all = aud["passed"] == aud["total"]
        st.markdown(cards([
            card("Checks passing", f"{aud['passed']} / {aud['total']}", f"run {aud['run_at']}", tone="pos" if ok_all else "neg"),
            *[card(area, f"{int(g.passed.sum())} / {len(g)}", "all pass" if g.passed.all() else "see failures below", tone="pos" if g.passed.all() else "neg")
              for area, g in list(df_a.groupby("area", sort=False))[:3]],
        ]), unsafe_allow_html=True)
        rows = "".join(f'<tr><td>{r_.area}</td><td style="text-align:left">{r_.check}</td><td style="text-align:left">{r_.detail}</td>'
                       f'<td><span class="pill {"ok" if r_.passed else ""}">{"PASS" if r_.passed else "FAIL"}</span></td></tr>'
                       for r_ in df_a.itertuples())
        with st.expander(f"All {aud['total']} checks"):
            st.markdown(f'<div class="wrap"><table class="fin"><tr><th>Area</th><th style="text-align:left">Check</th>'
                        f'<th style="text-align:left">Detail</th><th>Status</th></tr>{rows}</table></div>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.markdown('<div class="note">No audit has been run yet: <code>py -3.12 audit.py</code>.</div>', unsafe_allow_html=True)
    st.markdown('<div class="note"><b>Not investment advice.</b> This is a modelling exercise. Outputs depend on the assumptions chosen and are not a recommendation to buy or sell any security.</div>', unsafe_allow_html=True)
