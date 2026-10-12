"""Deal tab: Shell acquires BP."""
from __future__ import annotations
from dataclasses import replace
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from model.ma import DealInputs, run_deal, sensitivity_accretion, breakeven_synergies
from model.pipeline import Settings
from ui.theme import GOLD, GOLD_SOFT, IVORY, MUTED, WINE, SLATE, card, cards, style_fig, table_html


def _bn(x: float, d: int = 1) -> str:
    return f"${x/1e3:,.{d}f}bn"


def _pct(x: float, d: int = 1, sign: bool = True) -> str:
    return f"{x*100:+.{d}f}%" if sign else f"{x*100:.{d}f}%"


@st.cache_data(show_spinner="Building the pro forma company…")
def _deal(S: Settings, d: DealInputs) -> dict:
    return run_deal(S, d)


@st.cache_data(show_spinner="Running sensitivities…")
def _grid(S: Settings, d: DealInputs, rows: tuple, cols: tuple, row_attr: str, col_attr: str, year_index: int, metric):
    return sensitivity_accretion(S, d, list(rows), list(cols), row_attr, col_attr, year_index, metric)


@st.cache_data(show_spinner=False)
def _breakeven(S: Settings, d: DealInputs) -> float:
    return breakeven_synergies(S, d, year_index=2)


def _heat(df: pd.DataFrame, title: str, xlab: str, ylab: str, fmt_x, fmt_y, centre: float = 0.0) -> go.Figure:
    z = df.values.astype(float)
    h = go.Figure(go.Heatmap(
        z=np.clip(z - centre, -0.3, 0.3), x=[fmt_x(c) for c in df.columns], y=[fmt_y(r) for r in df.index],
        text=[[f"{v*100:+.0f}%" for v in row] for row in z], texttemplate="%{text}", textfont=dict(size=13, color=IVORY),
        showscale=False, xgap=3, ygap=3, zmid=0,
        colorscale=[[0, "#6E2F3C"], [0.45, "#2A1A20"], [0.5, "#1B1B20"], [0.55, "#3A3220"], [1, "#B8975A"]],
        hovertemplate=f"{ylab} %{{y}} · {xlab} %{{x}}<br>%{{text}}<extra></extra>"))
    style_fig(h, 320)
    h.update_layout(title=title, margin=dict(l=80, r=18, t=60, b=44), xaxis_title=xlab)
    h.update_yaxes(type="category", autorange="reversed", title_text=ylab); h.update_xaxes(type="category")
    return h


def render(S: Settings) -> None:
    st.markdown('<div class="section" style="margin-top:6px">Shell acquires BP</div>'
                '<div class="lede">A stock-and-cash takeover of BP by Shell, closing at the end of 2026. Both companies are forecast on their own, '
                'purchase accounting builds the combined opening balance sheet, and the enlarged group is then forecast with phased synergies, '
                'integration costs and a new acquisition loan that is repaid from excess cash. This is a modelling exercise, not a proposal; the combination would face '
                'severe competition-law and political scrutiny. The operating case (Bear/Base/Bull and adjustments) follows the sidebar.</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    premium = c1.slider("Premium to BP’s share price", 0, 70, 30, 1, key="ma_prem") / 100
    pct_stock = c2.slider("Paid in Shell shares", 0, 100, 50, 5, key="ma_stock", help="The rest is cash, funded by new debt.") / 100
    syn = c3.slider("Run-rate synergies ($bn, pre-tax)", 0.0, 8.0, 3.0, 0.25, key="ma_syn") * 1000
    divest = c4.slider("BP divested for competition (% of EBITDA)", 0, 30, 0, 1, key="ma_div") / 100

    with st.expander("Costs, accounting and financing settings"):
        a1, a2, a3, a4 = st.columns(4)
        integ = a1.slider("Integration cost (x run-rate synergies)", 0.0, 3.0, 1.2, 0.1, key="ma_int")
        spread = a2.slider("New debt spread over risk-free", 0.0, 3.0, 1.0, 0.1, key="ma_spread") / 100
        writeup = a3.slider("Fair-value uplift on BP fixed assets", 0, 20, 8, 1, key="ma_wu") / 100
        bb = a4.slider("Shell buybacks continued after the deal", 0, 100, 0, 10, key="ma_bb") / 100
        b1, b2, b3, b4 = st.columns(4)
        adv = b1.slider("Advisory fees (% of EV)", 0.0, 1.0, 0.3, 0.05, key="ma_adv") / 100
        fin = b2.slider("Financing fees (% of new debt)", 0.0, 3.0, 1.0, 0.25, key="ma_fin") / 100
        cash_bs = b3.slider("Cash consideration funded from cash ($bn)", 0.0, 30.0, 0.0, 1.0, key="ma_cash") * 1000
        flag = b4.slider("Leverage flag (net debt / EBITDA)", 1.5, 4.0, 2.5, 0.1, key="ma_flag")

    d = DealInputs(premium=premium, pct_stock=pct_stock, synergies_runrate=syn, integration_cost_multiple=integ, new_debt_spread=spread,
                   ppa_writeup_pct=writeup, buyback_pct=bb, advisory_fee_pct=adv, financing_fee_pct=fin, cash_from_balance_sheet=cash_bs,
                   divest_pct_ebitda=divest, max_leverage_flag=flag)
    r = _deal(S, d)
    su, acc, cr, val, ppa = r["su"], r["accretion"], r["credit"], r["value"], r["ppa"]
    y = r["years"]
    fx = val["fx"]
    be = _breakeven(S, d)

    for f in r["flags"]:
        st.markdown(f'<div class="note" style="border-left-color:#9B4A5A">{f}</div>', unsafe_allow_html=True)

    tone = lambda v: "pos" if v >= 0 else "neg"
    st.markdown(cards([
        card("Offer per BP share", f"{su['offer_gbp_pence']:,.0f}", f"{premium*100:.0f}% premium to {r['B']['market']['price_gbp_pence']:,.0f}p", "p"),
        card("Equity price · enterprise value", _bn(su["uses"]["Equity purchase price"], 0), f"EV {_bn(su['ev_target'], 0)} incl. net debt and hybrids"),
        card("BP holders own", _pct(su["ownership_bp"], 1, False), f"{su['new_shares_m']:,.0f}m new Shell shares · {pct_stock*100:.0f}% stock"),
        card("Leverage at close", f"{r['leverage']['pro_forma_close']:.1f}x", f"net debt / EBITDA, from {r['leverage']['shell_before']:.1f}x at Shell today"),
    ]), unsafe_allow_html=True)
    st.markdown(cards([
        card("EPS accretion · year 1", _pct(acc.loc["accretion", y[0]]), f"{y[0]} · adjusted {_pct(acc.loc['adj_accretion', y[0]])}", tone=tone(acc.loc["accretion", y[0]])),
        card("EPS accretion · year 3", _pct(acc.loc["accretion", y[2]]), f"{y[2]} · adjusted {_pct(acc.loc['adj_accretion', y[2]])}", tone=tone(acc.loc["accretion", y[2]])),
        card("Intrinsic value per Shell share", _pct(val["intrinsic_accretion"]), f"{val['intrinsic_before_usd']/fx*100:,.0f}p to {val['intrinsic_after_usd']/fx*100:,.0f}p (DCF basis)", tone=tone(val["intrinsic_accretion"])),
        card("Premium vs synergy value", f"{val['premium_share_of_synergies']*100:,.0f}%" if np.isfinite(val["premium_share_of_synergies"]) else "n/m",
             f"{_bn(val['premium_usd'])} premium against {_bn(val['pv_synergies'])} PV of synergies"),
    ]), unsafe_allow_html=True)

    # ── sources and uses
    st.markdown('<div class="section">Funding the deal</div>', unsafe_allow_html=True)
    fig = go.Figure()
    for (k, v), c in zip({k: v for k, v in su["sources"].items() if v > 1}.items(), [GOLD, SLATE, "#7A7F8C", "#A0A4AE"]):
        fig.add_trace(go.Bar(y=["Sources"], x=[v / 1e3], orientation="h", name=k, marker=dict(color=c, line=dict(color="#0A0A0C", width=1)), text=[f"{k}<br>{v/1e3:,.1f}"],
                             textposition="inside", insidetextanchor="middle", textfont=dict(size=11, color="#0A0A0C" if c == GOLD else IVORY), hovertemplate=f"{k}: $%{{x:,.1f}}bn<extra></extra>"))
    for (k, v), c in zip(su["uses"].items(), [GOLD, "#8A7A55", "#6E6248"]):
        fig.add_trace(go.Bar(y=["Uses"], x=[v / 1e3], orientation="h", name=k, marker=dict(color=c, line=dict(color="#0A0A0C", width=1)),
                             text=[f"{k}<br>{v/1e3:,.1f}" if v / sum(su["uses"].values()) > 0.06 else ""], textposition="inside", insidetextanchor="middle", textfont=dict(size=11, color=IVORY),
                             hovertemplate=f"{k}: $%{{x:,.2f}}bn<extra></extra>"))
    style_fig(fig, 230)
    fig.update_layout(barmode="stack", xaxis_title="USD bn", margin=dict(l=18, r=18, t=18, b=40))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # ── EPS accretion
    cL, cR = st.columns(2)
    with cL:
        eps = make_subplots(specs=[[{"secondary_y": True}]])
        yl = [f"{v}E" for v in y]
        eps.add_trace(go.Bar(x=yl, y=acc.loc["standalone_eps"], name="Shell standalone", marker=dict(color=SLATE)), secondary_y=False)
        eps.add_trace(go.Bar(x=yl, y=acc.loc["pro_forma_eps"], name="Pro forma", marker=dict(color=GOLD_SOFT, line=dict(color=GOLD, width=1))), secondary_y=False)
        eps.add_trace(go.Scatter(x=yl, y=acc.loc["accretion"] * 100, name="Accretion (%, right)", mode="lines+markers+text", line=dict(color=IVORY, width=2),
                                 text=[f"{v*100:+.0f}%" for v in acc.loc["accretion"]], textposition="top center", textfont=dict(size=11, color=IVORY)), secondary_y=True)
        style_fig(eps, 390, legend=True)
        eps.update_layout(barmode="group", title="Earnings per share (USD)", margin=dict(l=18, r=50, t=70, b=40))
        eps.update_yaxes(title_text="USD per share", secondary_y=False, rangemode="tozero"); eps.update_yaxes(title_text="%", secondary_y=True, showgrid=False, rangemode="tozero")
        st.plotly_chart(eps, width="stretch", config={"displayModeBar": False})
    with cR:
        con = r["contribution"]
        cf = go.Figure()
        cf.add_trace(go.Bar(y=list(con.index), x=con["shell"] * 100, orientation="h", name="Shell", marker=dict(color=SLATE), text=[f"{v*100:.0f}%" for v in con["shell"]],
                            textposition="inside", textfont=dict(color=IVORY)))
        cf.add_trace(go.Bar(y=list(con.index), x=con["bp"] * 100, orientation="h", name="BP", marker=dict(color=GOLD_SOFT, line=dict(color=GOLD, width=1)),
                            text=[f"{v*100:.0f}%" for v in con["bp"]], textposition="inside", textfont=dict(color=IVORY)))
        cf.add_vline(x=(1 - su["ownership_bp"]) * 100, line=dict(color=IVORY, width=1.4, dash="dash"),
                     annotation_text=f"Shell holders keep {su['ownership_shell']*100:.0f}%", annotation_font=dict(size=11, color=IVORY), annotation_position="top")
        style_fig(cf, 390, legend=True)
        cf.update_layout(barmode="stack", title="Who contributes what, year 1 (%)", xaxis=dict(range=[0, 100], title="Share of combined"), margin=dict(l=18, r=18, t=70, b=40))
        cf.update_yaxes(autorange="reversed")
        st.plotly_chart(cf, width="stretch", config={"displayModeBar": False})

    tbl = acc.loc[["standalone_eps", "pro_forma_eps", "accretion", "adj_pro_forma_eps", "adj_accretion", "synergies_pre_tax", "integration_costs_pre_tax", "ppa_stepup_da"]].copy()
    tbl.columns = [f"{c}E" for c in tbl.columns]
    st.markdown(table_html(tbl, {"standalone_eps": "Shell standalone EPS (USD)", "pro_forma_eps": "Pro forma EPS (USD)", "accretion": "Accretion / (dilution)",
                                 "adj_pro_forma_eps": "Adjusted pro forma EPS (ex integration costs and PPA)", "adj_accretion": "Adjusted accretion",
                                 "synergies_pre_tax": "Synergies, pre-tax (USD m)", "integration_costs_pre_tax": "Integration costs, pre-tax (USD m)", "ppa_stepup_da": "PPA step-up depreciation (USD m)"},
                           totals={"accretion", "adj_accretion"}, pct_rows={"accretion", "adj_accretion"}, digits=2,
                           row_digits={"synergies_pre_tax": 0, "integration_costs_pre_tax": 0, "ppa_stepup_da": 0}), unsafe_allow_html=True)
    if be == 0:
        be_txt = "On these terms the deal is already accretive in year 3 with no synergies at all."
    elif np.isnan(be):
        be_txt = "On these terms EPS cannot break even in year 3 within $20bn of synergies."
    else:
        be_txt = f"On these terms EPS is neutral in year 3 at {_bn(be)} of run-rate synergies."
    st.markdown(f'<div class="note"><b>Breakeven.</b> {be_txt} '
                f'EPS is measured on a constant share count for both cases, and the standalone comparator follows the same buyback policy, so the comparison is like-for-like. '
                f'Accretion is large partly because Shell’s debt is cheap relative to BP’s earnings yield; that is a financing effect, not proof of value creation.</div>', unsafe_allow_html=True)

    # ── value creation + PPA
    st.markdown('<div class="section">Value to Shell’s shareholders</div><div class="lede">EPS accretion says little about value. Two tests do: '
                'how the premium compares with the synergies it buys, and what each Shell share is worth on a DCF basis with and without the deal.</div>', unsafe_allow_html=True)
    vL, vR = st.columns(2)
    with vL:
        vf = go.Figure()
        vf.add_trace(go.Bar(x=["Premium paid to BP holders"], y=[val["premium_usd"] / 1e3], marker=dict(color=WINE), text=[f"{val['premium_usd']/1e3:,.1f}"], textposition="outside", textfont=dict(color=IVORY)))
        vf.add_trace(go.Bar(x=["PV of synergies"], y=[val["pv_synergies"] / 1e3], marker=dict(color=GOLD), text=[f"{val['pv_synergies']/1e3:,.1f}"], textposition="outside", textfont=dict(color=IVORY)))
        vf.add_trace(go.Bar(x=["Integration costs + fees"], y=[(val["pv_integration"] + val["fees"]) / 1e3], marker=dict(color=SLATE),
                            text=[f"{(val['pv_integration'] + val['fees'])/1e3:,.1f}"], textposition="outside", textfont=dict(color=IVORY)))
        style_fig(vf, 360)
        vf.update_layout(title="Premium against synergies (USD bn)", showlegend=False, yaxis_title="USD bn", margin=dict(l=18, r=18, t=60, b=40))
        st.plotly_chart(vf, width="stretch", config={"displayModeBar": False})
    with vR:
        items = [("Book equity of BP", ppa["book_equity_parent"]), ("Existing goodwill removed", ppa["less_existing_goodwill"]), ("Fair-value uplift", ppa["plus_fair_value_writeup"]),
                 ("Deferred tax on uplift", ppa["less_deferred_tax"])]
        if abs(ppa["divestment_adjustment"]) > 1:
            items.append(("Divestment adjustment", -ppa["divestment_adjustment"]))
        wf = go.Figure(go.Waterfall(
            x=[k for k, _ in items] + ["Goodwill created", "Price paid"], measure=["absolute"] + ["relative"] * (len(items) - 1) + ["relative", "total"],
            y=[v / 1e3 for _, v in items] + [ppa["goodwill_created"] / 1e3, 0], connector=dict(line=dict(color="rgba(237,230,214,.25)", width=1)),
            increasing=dict(marker=dict(color=GOLD)), decreasing=dict(marker=dict(color=WINE)), totals=dict(marker=dict(color=IVORY)),
            text=[f"{v/1e3:+,.1f}" if i else f"{v/1e3:,.1f}" for i, (_, v) in enumerate(items)] + [f"{ppa['goodwill_created']/1e3:+,.1f}", f"{ppa['equity_purchase_price']/1e3:,.1f}"],
            textposition="outside", textfont=dict(size=11, color=IVORY), hovertemplate="%{x}: $%{y:,.1f}bn<extra></extra>"))
        style_fig(wf, 360)
        wf.update_layout(title="Purchase price allocation (USD bn)", yaxis_title="USD bn", margin=dict(l=18, r=18, t=60, b=60))
        st.plotly_chart(wf, width="stretch", config={"displayModeBar": False})
    st.markdown(
        f'<div class="note"><b>Reading the DCF test.</b> It values Shell at {_bn(val["standalone_equity_shell"], 0)} and BP at {_bn(val["standalone_equity_bp"], 0)} using this model’s own assumptions, '
        f'against market values of {_bn(val["shell_market_cap"], 0)} and {_bn(val["bp_market_cap"], 0)}. When the DCF says Shell is worth less than the market does and BP more, paying in Shell stock looks '
        f'attractive almost by construction. The result is only as good as that gap: change the sidebar assumptions and watch it move.</div>', unsafe_allow_html=True)

    # ── credit
    st.markdown('<div class="section">The enlarged balance sheet</div>', unsafe_allow_html=True)
    lev = make_subplots(specs=[[{"secondary_y": True}]])
    yl = [f"{v}E" for v in y]
    lev.add_trace(go.Bar(x=["Close"] + yl, y=[su["sources"]["Acquisition debt"] / 1e3] + list(cr.loc["acquisition_debt"] / 1e3), name="Acquisition debt (USD bn)", marker=dict(color=SLATE)), secondary_y=False)
    lev.add_trace(go.Scatter(x=["Close"] + yl, y=[r["leverage"]["pro_forma_close"]] + list(cr.loc["net_debt_to_ebitda"]), name="Net debt / EBITDA (x, right)", mode="lines+markers",
                             line=dict(color=GOLD, width=2), marker=dict(size=6)), secondary_y=True)
    lev.add_hline(y=flag, line=dict(color=WINE, width=1, dash="dot"), secondary_y=True, annotation_text="flag level", annotation_font=dict(size=10, color=MUTED))
    style_fig(lev, 340, legend=True)
    lev.update_layout(title="Paying down the acquisition debt", margin=dict(l=18, r=50, t=70, b=40))
    lev.update_yaxes(title_text="USD bn", secondary_y=False); lev.update_yaxes(title_text="x", secondary_y=True, showgrid=False, rangemode="tozero")
    st.plotly_chart(lev, width="stretch", config={"displayModeBar": False})
    crt = cr.copy(); crt.columns = [f"{c}E" for c in crt.columns]
    st.markdown(table_html(crt, {"net_debt": "Net debt (USD m)", "net_debt_to_ebitda": "Net debt / EBITDA", "acquisition_debt": "Acquisition debt (USD m)",
                                 "interest_cover": "EBITDA / interest", "dividend_cover_fcf": "Free cash flow / dividends"}, mult_rows={"net_debt_to_ebitda", "interest_cover", "dividend_cover_fcf"}), unsafe_allow_html=True)

    # ── sensitivities
    st.markdown('<div class="section">Sensitivity</div><div class="lede">Where the deal stops making sense. Gold cells are accretive, wine cells dilutive.</div>', unsafe_allow_html=True)
    prem_grid = (0.0, 0.15, 0.30, 0.45, 0.60)
    g1 = _grid(S, d, prem_grid, (0.0, 0.25, 0.5, 0.75, 1.0), "premium", "pct_stock", 1, "accretion")
    both = _grid(S, d, prem_grid, (0.0, 1500.0, 3000.0, 4500.0, 6000.0), "premium", "synergies_runrate", 0,
                 (("accretion", 2), ("intrinsic", 0)))
    g2, g3 = both[("accretion", 2)], both[("intrinsic", 0)]
    s1, s2 = st.columns(2)
    with s1:
        st.plotly_chart(_heat(g1, "EPS accretion, year 2 · premium vs % stock", "Paid in stock", "Premium", lambda c: f"{c*100:.0f}%", lambda r_: f"{r_*100:.0f}%"), width="stretch", config={"displayModeBar": False})
    with s2:
        st.plotly_chart(_heat(g2, "EPS accretion, year 3 · premium vs synergies", "Run-rate synergies", "Premium", lambda c: f"${c/1e3:.1f}bn", lambda r_: f"{r_*100:.0f}%"), width="stretch", config={"displayModeBar": False})
    st.plotly_chart(_heat(g3, "Intrinsic value per Shell share (DCF basis) · premium vs synergies", "Run-rate synergies", "Premium", lambda c: f"${c/1e3:.1f}bn", lambda r_: f"{r_*100:.0f}%"), width="stretch", config={"displayModeBar": False})

    # ── pro forma statements
    st.markdown('<div class="section">Pro forma financials</div>', unsafe_allow_html=True)
    sub = st.tabs(["Income statement", "Balance sheet", "Cash flow"])
    pf = r["pf"]
    show = lambda df: df.rename(columns=lambda c: f"{c}E")
    with sub[0]:
        st.markdown(table_html(show(pf["income_statement"]), {"revenue": "Revenue", "ebitda": "EBITDA", "da": "Depreciation & amortisation (incl. PPA)", "ebit": "Operating EBIT",
            "interest_expense": "Interest expense", "interest_income": "Interest income", "pbt_ex_jv": "Pre-tax profit (ex-JV, after one-offs)", "tax": "Tax", "jv_income": "Share of JV profit",
            "net_income": "Net income", "net_income_minorities": "Minorities (hybrid coupons)", "net_income_parent": "Net income to shareholders", "one_off_costs": "Integration costs",
            "interest_on_acquisition_debt": "of which interest on acquisition debt"}, totals={"revenue", "ebit", "net_income", "net_income_parent"}), unsafe_allow_html=True)
    with sub[1]:
        ob = pd.Series(r["opening"]).rename("Close")
        bs = pf["balance_sheet"].copy(); bs.columns = [f"{c}E" for c in bs.columns]
        st.markdown(table_html(bs, {"cash": "Cash", "receivables": "Receivables", "inventories": "Inventories", "fixed_assets": "Fixed assets incl. right-of-use", "goodwill": "Goodwill",
            "other_assets": "Other assets", "total_assets": "Total assets", "payables": "Payables", "borrowings": "Borrowings", "revolver": "Revolver", "acquisition_debt": "Acquisition debt",
            "leases": "Lease liabilities", "other_liabilities": "Other liabilities (incl. deferred tax)", "total_liabilities": "Total liabilities", "equity_parent": "Shareholders’ equity",
            "minorities": "Minorities", "total_equity": "Total equity", "balance_check": "Balance check (should be 0)"}, totals={"total_assets", "total_liabilities", "total_equity"}), unsafe_allow_html=True)
        st.markdown(f'<span class="pill ok">Balance sheet balances</span> opening difference {abs(r["opening_check"]):.1e}, forecast {pf["balance_sheet"].loc["balance_check"].abs().max():.1e}', unsafe_allow_html=True)
    with sub[2]:
        st.markdown(table_html(show(pf["cash_flow"]), {"net_income": "Net income", "da": "Depreciation & amortisation", "change_in_nwc": "Change in working capital", "cfo": "Cash from operations",
            "capex": "Capital expenditure", "cfi": "Cash from investing", "net_debt_issuance": "Net debt issued", "revolver_draw_repay": "Revolver draw / (repay)", "dividends": "Dividends",
            "buybacks": "Share buybacks", "minority_distributions": "Minority distributions", "lease_principal": "Lease principal", "cff": "Cash from financing",
            "net_change_in_cash": "Net change in cash", "closing_cash": "Closing cash", "acquisition_debt_repayment": "Acquisition debt repaid"}, totals={"cfo", "cfi", "cff", "closing_cash"}), unsafe_allow_html=True)

    with st.expander("Assumptions and what this does not capture"):
        st.markdown(
            f'<div class="note"><b>Terms.</b> BP is bought at {premium*100:.0f}% over its current share price ({r["B"]["market"]["price_gbp_pence"]:,.0f}p), {pct_stock*100:.0f}% in new Shell shares issued at Shell’s current price. '
            f'Cash is funded by a new loan at the risk-free rate plus {spread*1e4:.0f}bp, swept down with excess cash before any buybacks. Advisory and financing fees are expensed at close.<br>'
            f'<b>Accounting.</b> IFRS 3: BP’s book equity, less its existing goodwill, plus a {writeup*100:.0f}% fair-value uplift on fixed assets (depreciated over 15 years, with deferred tax), gives the net assets acquired; the rest of the price is goodwill. '
            f'The cash effect of unwinding the deferred tax (about $0.1bn a year) is ignored.<br>'
            f'<b>Operations.</b> Synergies phase in 33% / 67% / 100% and are taxed at the combined rate; integration costs are spread over the first two years. Dividend per share follows Shell’s standalone path on the enlarged share count. '
            f'BP’s hybrid coupons are carried as fixed minority charges. Both companies use the same operating-case settings.<br>'
            f'<b>Not modelled.</b> Competition-remedy details beyond the simple divestment lever, change-of-control clauses, financing in other currencies, rating-agency reactions, share-price moves on announcement, '
            f'tax leakage on divestments, and any cultural or execution risk. EPS holds share counts constant on both sides and is not a substitute for a value test.</div>', unsafe_allow_html=True)
