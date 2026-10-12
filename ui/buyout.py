"""Buyout tab: carve-out LBO of a Shell division."""
from __future__ import annotations
from dataclasses import replace
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model.lbo import (run, sensitivity_irr, sensitivity_leverage, max_entry_multiple, breakeven_margin_shock,
                       irr_by_exit_year, N_PROJ)
from model.lbo_setup import default_inputs, shell_group_multiple
from model.segments import SEGMENTS, SHORT, profile
from ui.theme import GOLD, GOLD_SOFT, IVORY, MUTED, WINE, SLATE, card, cards, style_fig, table_html

DIV_NOTES = {
    "Marketing": "Retail fuel, convenience and lubricants. Stable, cash-generative and moderately capital-intensive: the classic sponsor profile.",
    "Chemicals and Products": "Refining and petrochemicals. Earnings have fallen for three years and capex absorbs most of the cash flow: a stress test for the structure.",
    "Integrated Gas": "LNG and gas-to-liquids. High margins, but the scale is far beyond any sponsor-sized deal.",
    "Renewables and Energy Solutions": "Power, trading and low-carbon. EBITDA is close to zero, so a leveraged structure cannot service its debt.",
}


@st.cache_data(show_spinner="Running the buyout…")
def _analyse(inp, target: float):
    """Everything the tab needs for one set of inputs, cached so unrelated reruns cost nothing."""
    res = run(inp)  # base case for these inputs
    en = [round(inp.entry_multiple + d, 2) for d in (-1.5, -0.75, 0, 0.75, 1.5)]
    ex = [round(inp.exit_mult + d, 2) for d in (-1.5, -0.75, 0, 0.75, 1.5)]
    return dict(res=res, mx=max_entry_multiple(inp, target), be=breakeven_margin_shock(inp, 0.0),
                g1=sensitivity_irr(inp, en, ex), g2=sensitivity_leverage(inp, [max(0.0, inp.tlb_x + d) for d in (-1.5, -0.75, 0, 0.75, 1.5)], ex),
                ey=irr_by_exit_year(inp, res))


def _bn(x: float, d: int = 1) -> str:
    return f"${x/1e3:,.{d}f}bn"


def _irr_txt(res: dict) -> str:
    if not res["financeable"]:
        return "n/m"
    irr = res["returns"]["irr"]
    return "total loss" if (np.isnan(irr) or irr <= -0.999) else f"{irr*100:.1f}%"


def render(S_company: str) -> None:
    gm = shell_group_multiple()
    st.markdown('<div class="section" style="margin-top:6px">Carve-out buyout</div>'
                '<div class="lede">What would a private-equity sponsor earn buying one Shell division, funding it with debt, and selling in a few years? '
                'Division financials come straight from Shell’s segment note (Form 20-F, note 7) and tie to the group accounts. '
                f'Shell itself trades at about <b>{gm:.1f}x</b> EBITDA, which is the default entry price.</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1])
    with c1:
        seg = st.selectbox("Division", SEGMENTS, index=2, format_func=SHORT.get, key="lbo_seg")
    with c2:
        case = st.radio("Operating case", ["downside", "base", "upside"], index=1, format_func=str.title, horizontal=True, key="lbo_case")
    with c3:
        entry = st.slider("Entry EV / EBITDA", 3.0, 12.0, float(round(gm * 2) / 2), 0.25, key="lbo_entry")
    with c4:
        same = st.toggle("Exit at entry multiple", value=True, key="lbo_same")
        exit_m = entry if same else st.slider("Exit EV / EBITDA", 3.0, 12.0, float(round(gm * 2) / 2), 0.25, key="lbo_exit")

    with st.expander("Financing, costs and returns settings"):
        a1, a2, a3, a4 = st.columns(4)
        tlb_x = a1.slider("Term loan B (x EBITDA)", 0.0, 6.0, 3.0, 0.25, key="lbo_tlb")
        notes_x = a2.slider("Senior notes (x)", 0.0, 3.0, 1.5, 0.25, key="lbo_notes")
        mezz_x = a3.slider("Mezzanine (x)", 0.0, 2.0, 0.5, 0.25, key="lbo_mezz")
        hold = a4.slider("Hold (years)", 3, N_PROJ, 5, key="lbo_hold")
        b1, b2, b3, b4 = st.columns(4)
        tlb_sp = b1.slider("TLB spread", 2.0, 6.0, 3.5, 0.25, key="lbo_sp") / 100
        notes_c = b2.slider("Notes coupon", 5.0, 11.0, 7.5, 0.25, key="lbo_nc") / 100
        sa = b3.slider("Standalone costs (% revenue)", 0.0, 1.0, 0.4, 0.05, key="lbo_sa") / 100
        tax = b4.slider("Tax rate", 15.0, 40.0, 28.0, 1.0, key="lbo_tax") / 100
        d1, d2, d3, d4 = st.columns(4)
        cap_on = d1.toggle("Cap interest deductibility at 30% of EBITDA", value=True, key="lbo_cap")
        sweep = d2.slider("Cash sweep", 0, 100, 100, 10, key="lbo_sweep") / 100
        target = d3.slider("Target IRR (for max price)", 10, 30, 20, 1, key="lbo_target") / 100
        promote = d4.slider("Management promote (% of gain)", 0, 20, 0, 1, key="lbo_prom") / 100

    inp = replace(default_inputs(seg, case), entry_multiple=entry, exit_multiple=exit_m, hold_years=hold,
                  tlb_x=tlb_x, notes_x=notes_x, mezz_x=mezz_x, tlb_spread=tlb_sp, notes_coupon=notes_c,
                  standalone_cost_pct=sa, tax_rate=tax, interest_cap_pct_ebitda=0.30 if cap_on else None,
                  sweep_pct=sweep, mgmt_promote_pct=promote)
    A_ = _analyse(inp, target)
    res = A_["res"]
    su, ret, proj = res["su"], res["returns"], res["projections"]
    prof = profile(seg)

    st.markdown(f'<div class="note"><b>{SHORT[seg]}.</b> {DIV_NOTES[seg]}</div>', unsafe_allow_html=True)
    if not res["financeable"]:
        st.markdown('<div class="note" style="border-left-color:#9B4A5A"><b>Not financeable as structured.</b> The revolver is exhausted and cash goes below the minimum. '
                    'Returns are shown as n/m: a deal that cannot pay its own debt has no meaningful IRR. Lower the debt or the price.</div>', unsafe_allow_html=True)

    mx, be = A_["mx"], A_["be"]
    tone = "pos" if (res["financeable"] and ret["irr"] >= target) else "neg"
    st.markdown(cards([
        card("Sponsor IRR", _irr_txt(res), f"{hold}-year hold · target {target*100:.0f}%", tone=tone),
        card("Money multiple", "n/m" if not res["financeable"] else f"{ret['moic']:.2f}x", f"Equity {_bn(ret['equity_in'])} in, {_bn(ret['equity_exit'])} out"),
        card("Equity cheque", _bn(su["equity"]), f"{su['equity']/su['total']*100:.0f}% of {_bn(su['total'])} total funding"),
        card(f"Max price for {target*100:.0f}% IRR", "n/m" if np.isnan(mx) else f"{mx:.1f}x",
             "n/m" if np.isnan(mx) else f"EV {_bn(mx*inp.ltm_ebitda)} · exit held at {inp.exit_mult:.1f}x"),
    ]), unsafe_allow_html=True)
    st.markdown(cards([
        card("Entry EV", _bn(su["ev"]), f"{inp.entry_multiple:.1f}x LTM EBITDA of {_bn(inp.ltm_ebitda)}"),
        card("Leverage at close", f"{su['debt']/su['pf_ebitda']:.1f}x", f"on pro-forma EBITDA {_bn(su['pf_ebitda'])} after standalone costs"),
        card("Interest cover, year 1", f"{proj.loc['interest_cover', 1]:.1f}x", "EBITDA / cash interest"),
        card("Margin cushion", f"{be*100:.1f}pp", "EBITDA-margin fall (every year) before IRR reaches 0%"),
    ]), unsafe_allow_html=True)
    for f in res["flags"]:
        if "liquidity shortfall" in f:
            continue
        st.markdown(f'<div class="note" style="border-left-color:#9B4A5A">{f}</div>', unsafe_allow_html=True)

    # ── sources & uses
    st.markdown('<div class="section">Sources and uses at close</div>', unsafe_allow_html=True)
    lab = {"term_loan_b": "Term loan B", "senior_notes": "Senior notes", "mezzanine": "Mezzanine (PIK)", "revolver_drawn": "Revolver (drawn)", "sponsor_equity": "Sponsor equity",
           "purchase_price": "Purchase price (EV)", "advisory_fees": "Advisory fees", "financing_fees": "Financing fees", "separation_costs": "Separation costs", "cash_to_balance_sheet": "Cash to balance sheet"}
    src = {k: v for k, v in su["sources"].items() if v > 0}
    fig = go.Figure()
    cols = [SLATE, "#7A7F8C", "#A0A4AE", GOLD]
    for (k, v), c in zip(src.items(), cols + [GOLD_SOFT] * 3):
        fig.add_trace(go.Bar(y=["Sources"], x=[v / 1e3], orientation="h", name=lab[k], marker=dict(color=c, line=dict(color="#0A0A0C", width=1)),
                             text=[f"{lab[k]}<br>{v/1e3:,.1f}"], textposition="inside", insidetextanchor="middle", textfont=dict(size=11, color="#0A0A0C" if c == GOLD else IVORY),
                             hovertemplate=f"{lab[k]}: $%{{x:,.1f}}bn<extra></extra>"))
    ucols = [GOLD, "#8A7A55", "#6E6248", "#54493A", "#3D362C"]
    for (k, v), c in zip(su["uses"].items(), ucols):
        fig.add_trace(go.Bar(y=["Uses"], x=[v / 1e3], orientation="h", name=lab[k], marker=dict(color=c, line=dict(color="#0A0A0C", width=1)),
                             text=[f"{lab[k]}<br>{v/1e3:,.1f}" if v / su["total"] > 0.07 else ""], textposition="inside", insidetextanchor="middle", textfont=dict(size=11, color=IVORY),
                             hovertemplate=f"{lab[k]}: $%{{x:,.2f}}bn<extra></extra>"))
    style_fig(fig, 250)
    fig.update_layout(barmode="stack", xaxis_title="USD bn", margin=dict(l=18, r=18, t=18, b=40))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # ── bridge + deleveraging
    cL, cR = st.columns(2)
    with cL:
        br = ret["bridge"]
        items = [(k, v) for k, v in br.items() if abs(v) > 1e-6]
        wf = go.Figure(go.Waterfall(
            x=["Equity invested"] + [k for k, _ in items] + ["Equity at exit"], measure=["absolute"] + ["relative"] * len(items) + ["total"],
            y=[ret["equity_in"] / 1e3] + [v / 1e3 for _, v in items] + [0], connector=dict(line=dict(color="rgba(237,230,214,.25)", width=1)),
            increasing=dict(marker=dict(color=GOLD)), decreasing=dict(marker=dict(color=WINE)), totals=dict(marker=dict(color=IVORY)),
            text=[f"{ret['equity_in']/1e3:,.1f}"] + [f"{v/1e3:+,.1f}" for _, v in items] + [f"{ret['equity_exit']/1e3:,.1f}"],
            textposition="outside", textfont=dict(size=11, color=IVORY), hovertemplate="%{x}: $%{y:,.1f}bn<extra></extra>"))
        style_fig(wf, 390)
        wf.update_layout(title="Where the return comes from (USD bn)", margin=dict(l=18, r=18, t=60, b=40), yaxis_title="USD bn")
        st.plotly_chart(wf, width="stretch", config={"displayModeBar": False})
    with cR:
        yrs = list(range(1, hold + 1))
        dbt = go.Figure()
        for k, nm, c in (("term_loan_b", "Term loan B", SLATE), ("senior_notes", "Senior notes", "#7A7F8C"), ("mezzanine", "Mezzanine", "#A0A4AE"), ("revolver", "Revolver", WINE)):
            dbt.add_trace(go.Bar(x=[f"Y{y}" for y in [0] + yrs], y=[(su["sources"].get({"term_loan_b": "term_loan_b", "senior_notes": "senior_notes", "mezzanine": "mezzanine", "revolver": "revolver_drawn"}[k], 0)) / 1e3] + [proj.loc[k, y] / 1e3 for y in yrs],
                                 name=nm, marker=dict(color=c)))
        dbt.add_trace(go.Scatter(x=[f"Y{y}" for y in [0] + yrs], y=[su["debt"] / su["pf_ebitda"]] + [proj.loc["debt_to_ebitda", y] for y in yrs], name="Debt / EBITDA (x, right)", yaxis="y2",
                                 mode="lines+markers", line=dict(color=GOLD, width=2), marker=dict(size=6)))
        style_fig(dbt, 390, legend=True)
        dbt.update_layout(barmode="stack", title="Paying the debt down (USD bn)", yaxis_title="USD bn", margin=dict(l=18, r=50, t=70, b=40),
                          yaxis2=dict(overlaying="y", side="right", showgrid=False, tickfont=dict(color=MUTED), title="x EBITDA"))
        st.plotly_chart(dbt, width="stretch", config={"displayModeBar": False})

    # ── sensitivities
    st.markdown('<div class="section">Sensitivity</div><div class="lede">IRR across price and exit assumptions. Cells at or above the target return are gold; below, wine.</div>', unsafe_allow_html=True)
    sA, sB = st.columns(2)
    g1, g2 = A_["g1"], A_["g2"]

    def heat(df, title):
        z = df.values.astype(float)
        zt = np.clip(z - target, -0.25, 0.25)
        h = go.Figure(go.Heatmap(z=zt, x=list(df.columns), y=list(df.index), text=[[("n/m" if np.isnan(v) else f"{v*100:.0f}%") for v in row] for row in z], texttemplate="%{text}",
                                 textfont=dict(size=13, color=IVORY), showscale=False, xgap=3, ygap=3, zmid=0,
                                 colorscale=[[0, "#6E2F3C"], [0.45, "#2A1A20"], [0.5, "#1B1B20"], [0.55, "#3A3220"], [1, "#B8975A"]],
                                 hovertemplate="%{y} entry · %{x} exit<br>IRR %{text}<extra></extra>"))
        style_fig(h, 320)
        h.update_layout(title=title, margin=dict(l=80, r=18, t=60, b=44), xaxis_title="Exit multiple")
        h.update_yaxes(type="category", autorange="reversed"); h.update_xaxes(type="category")
        return h
    with sA:
        st.plotly_chart(heat(g1, "IRR · entry vs exit multiple"), width="stretch", config={"displayModeBar": False})
    with sB:
        st.plotly_chart(heat(g2, "IRR · leverage vs exit multiple"), width="stretch", config={"displayModeBar": False})

    ey = A_["ey"]
    ex_fig = go.Figure(go.Bar(x=[f"Year {y}" for y in ey.index], y=ey["irr"] * 100, marker=dict(color=[GOLD if y == hold else GOLD_SOFT for y in ey.index]),
                              text=[f"{v*100:.1f}%" for v in ey["irr"]], textposition="outside", textfont=dict(size=11, color=IVORY), hovertemplate="%{x}: %{y:.1f}% IRR<extra></extra>"))
    style_fig(ex_fig, 280)
    ex_fig.update_layout(title="IRR by exit year", yaxis_title="IRR (%)", margin=dict(l=18, r=18, t=56, b=30))
    st.plotly_chart(ex_fig, width="stretch", config={"displayModeBar": False})

    # ── tables
    st.markdown('<div class="section">The division</div><div class="lede">Reported history (USD m). EBITDA is revenue less purchases and operating expenses; impairments, JV profit and divestment gains are excluded.</div>', unsafe_allow_html=True)
    hist = prof.loc[["revenue", "ebitda", "ebitda_margin", "da", "capex", "cash_conversion"]].copy()
    hist.columns = [str(c) for c in hist.columns]
    st.markdown(table_html(hist, {"revenue": "Revenue (incl. inter-segment)", "ebitda": "EBITDA", "ebitda_margin": "EBITDA margin", "da": "D&A (excl. impairments)",
                                  "capex": "Capital expenditure", "cash_conversion": "Cash conversion (EBITDA − capex) / EBITDA"},
                         totals={"ebitda"}, pct_rows={"ebitda_margin", "cash_conversion"}), unsafe_allow_html=True)

    st.markdown('<div class="section">Projections and credit statistics</div>', unsafe_allow_html=True)
    show = proj.loc[["revenue", "ebitda", "capex", "tax", "cfads", "cash_interest", "mandatory_amort", "sweep", "fcf", "total_debt", "net_debt", "debt_to_ebitda", "senior_to_ebitda", "interest_cover", "capex_cover"], list(range(1, hold + 1))].copy()
    show.columns = [f"Year {c}" for c in show.columns]
    st.markdown(table_html(show, {"revenue": "Revenue", "ebitda": "EBITDA (after standalone costs)", "capex": "Capital expenditure", "tax": "Cash tax", "cfads": "Cash flow before debt service",
                                  "cash_interest": "Cash interest", "mandatory_amort": "Mandatory amortisation", "sweep": "Cash sweep", "fcf": "Free cash flow after interest", "total_debt": "Total debt",
                                  "net_debt": "Net debt", "debt_to_ebitda": "Debt / EBITDA", "senior_to_ebitda": "Senior debt / EBITDA", "interest_cover": "EBITDA / cash interest",
                                  "capex_cover": "(EBITDA − capex) / cash interest"}, totals={"cfads", "total_debt"},
                         mult_rows={"debt_to_ebitda", "senior_to_ebitda", "interest_cover", "capex_cover"}), unsafe_allow_html=True)

    with st.expander("Assumptions and what this does not capture"):
        st.markdown(
            f'<div class="note"><b>Entry.</b> Cash-free, debt-free purchase at {inp.entry_multiple:.1f}x reported LTM EBITDA; Shell’s own implied multiple is {gm:.1f}x. No control premium or comparable-deal evidence is applied. '
            f'<b>Standalone costs</b> of {inp.standalone_cost_pct*100:.2f}% of revenue are deducted from projected EBITDA and from the lenders’ pro-forma EBITDA; separation costs are one-off.<br>'
            f'<b>Operating case.</b> Base holds the LTM margin ({inp.ebitda_margin[0]*100:.1f}%); downside fades it to the three-year average less 0.5pp by year 3; upside adds 0.8pp. Revenue growth follows the group placeholder view. '
            f'Division working capital is not disclosed, so the group ratio ({inp.nwc_pct*100:.1f}% of revenue) is used.<br>'
            f'<b>Financing.</b> Floating rate = US 13-week T-bill ({inp.base_rate*100:.2f}%) plus spread. Interest is on average balances; the mezzanine accretes PIK. Debt is capped at {inp.max_ltv*100:.0f}% of purchase price. '
            f'Net interest deductibility is optionally capped at 30% of EBITDA; disallowed interest is not carried forward.<br>'
            f'<b>Not modelled.</b> Dividend recaps, covenant resets, management equity beyond the promote, inter-segment contracts changing on separation, the Corporate segment’s cost allocation, and any tax leakage on the carve-out itself. '
            f'Inter-segment revenue is assumed to continue at arm’s length.'
            + (f'<br><b>Scale.</b> At ${su["ev"]/1e3:,.0f}bn this would rank among the largest buyouts ever attempted; read it as an illustration of the economics, not a deal that could be financed.' if su["ev"] > 40_000 else '')
            + '</div>', unsafe_allow_html=True)
