"""Merger model: Shell (acquirer) buys BP (target).

Approach
- The deal closes on 31 Dec of `close_year` (default 2026). Both companies are forecast standalone with the 3-statement
  engine; the opening pro forma balance sheet is built with IFRS 3 purchase accounting; the combined company is then
  forecast by running the same engine on the pro forma balance sheet and combined operating drivers.
- Combined operating lines = Shell + BP (less any divested slice of BP) + phased synergies - PPA step-up depreciation.
  Financing is rebuilt from scratch for the combined entity: existing debt of both, a new acquisition-debt tranche
  (swept with excess cash, ahead of buybacks), the acquirer's dividend per share paid on the enlarged share count, and
  integration costs as a one-off charge.
- EPS accretion holds share counts constant on both sides (standalone Shell vs pro forma Shell + new shares), and
  the standalone comparator is re-run with the same buyback policy so the two cases are like-for-like.
- A DCF-based value-creation view compares intrinsic value per Shell share with and without the deal.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from functools import lru_cache
import numpy as np
import pandas as pd

from model.pipeline import Settings, compute
from model.three_statement import Assumptions, forecast, forecast_from, BASE_YEAR

PF_YEARS = 5


@dataclass(frozen=True)
class DealInputs:
    premium: float = 0.30                  # to BP's current share price
    pct_stock: float = 0.50                # share of the equity price paid in new Shell shares
    synergies_runrate: float = 3_000.0     # USD m pre-tax, annual, at full run-rate
    synergy_phasing: tuple = (0.33, 0.67, 1.0, 1.0, 1.0)
    integration_cost_multiple: float = 1.2 # x run-rate synergies, spread 50/50 over years 1-2
    advisory_fee_pct: float = 0.003        # of target enterprise value
    financing_fee_pct: float = 0.010       # of acquisition debt, expensed at close
    ppa_writeup_pct: float = 0.08          # fair-value uplift on BP's fixed assets
    writeup_life_years: int = 15
    dtl_rate: float = 0.25                 # deferred tax on the write-up
    divest_pct_ebitda: float = 0.0         # regulatory remedy: share of BP sold at close
    divest_multiple: float = 6.0
    new_debt_spread: float = 0.010         # over the risk-free rate
    cash_from_balance_sheet: float = 0.0   # USD m of the cash consideration funded from existing cash
    buyback_pct: float = 0.0               # share of Shell's standalone buybacks kept after the deal
    acq_sweep_pct: float = 1.0             # excess cash used to repay acquisition debt first
    max_leverage_flag: float = 2.5         # net debt / EBITDA above which the deal is flagged


def _usd_price(m: dict, fx: float) -> float:
    return m["price_gbp_pence"] / 100 * fx


def _slice(bs: pd.Series, x: float) -> dict:
    """BP balance-sheet lines carried into the combined company, after removing the divested share x."""
    keep = 1 - x
    return {k: bs[k] * keep for k in ("receivables", "inventories", "fixed_assets", "other_assets", "payables", "other_liabilities", "leases")}


@lru_cache(maxsize=32)
def standalone(S: Settings) -> tuple[dict, dict]:
    """Standalone Shell and BP results; independent of the deal terms, so cached across a sensitivity grid."""
    return compute(replace(S, company="shell", mc_n=200)), compute(replace(S, company="bp", mc_n=200))


def run_deal(S: Settings, d: DealInputs) -> dict:
    A, B = standalone(S)
    fx = A["common"]["gbpusd"]
    n_years = PF_YEARS
    y0 = BASE_YEAR + 1                      # close at end of this year (2026): the last pre-deal year
    yrs_pf = list(range(y0 + 1, y0 + 1 + n_years))

    bsA, bsB = A["out"]["balance_sheet"], B["out"]["balance_sheet"]
    isA, isB = A["out"]["income_statement"], B["out"]["income_statement"]
    a_s, a_b = A["a"], B["a"]
    x = d.divest_pct_ebitda
    keep = 1 - x

    # ── prices, shares, consideration
    px_s, px_b = _usd_price(A["market"], fx), _usd_price(B["market"], fx)
    shares_s, shares_b = A["market"]["shares_m"], B["market"]["shares_m"]
    mcap_s, mcap_b = shares_s * px_s, shares_b * px_b
    P = mcap_b * (1 + d.premium)                           # equity purchase price
    S_stock = P * d.pct_stock
    C_cash = P - S_stock
    n_new = S_stock / px_s
    shares_pf = shares_s + n_new
    ownership_bp = n_new / shares_pf

    bB = bsB[y0]
    bA = bsA[y0]
    nd_b = bB["borrowings"] + bB["revolver"] + bB["leases"] - bB["cash"]
    ev_target = P + nd_b + bB["minorities"]
    adv = d.advisory_fee_pct * ev_target

    ebitda_b = float(isB.loc["ebitda", y0])
    proceeds = d.divest_multiple * x * ebitda_b
    # financing fee is a % of the debt it finances: D = (C + adv - cash_used - proceeds) / (1 - f)
    D_new = max((C_cash + adv - d.cash_from_balance_sheet - proceeds) / (1 - d.financing_fee_pct), 0.0)
    fin_fee = d.financing_fee_pct * D_new
    cash_used = d.cash_from_balance_sheet
    # general cash identity at close: any proceeds not needed for the deal (e.g. an all-stock deal with a divestment)
    # stay in the combined company as cash
    cash_change = D_new + proceeds - C_cash - adv - fin_fee
    surplus = max(cash_change + cash_used, 0.0)

    # ── purchase price allocation
    e_b = float(bB["equity_parent"])
    gw_b_old = float(bB["goodwill"])
    writeup = d.ppa_writeup_pct * float(bB["fixed_assets"]) * keep
    dtl = writeup * d.dtl_rate
    fv_net_assets = e_b - gw_b_old + writeup - dtl
    goodwill_new = P - fv_net_assets
    sl = _slice(bB, x)
    k_book = x * (bB["fixed_assets"] + bB["receivables"] + bB["inventories"] + bB["other_assets"]
                  - bB["payables"] - bB["other_liabilities"] - bB["leases"])
    goodwill_adj = k_book - proceeds                       # divested slice sold at `proceeds` vs its carrying value
    goodwill_total = float(bA["goodwill"]) + goodwill_new + goodwill_adj

    opening = dict(
        revenue=float(isA.loc["revenue", y0] + keep * isB.loc["revenue", y0]),
        cash=float(bA["cash"] + bB["cash"] + cash_change),
        receivables=float(bA["receivables"]) + sl["receivables"], inventories=float(bA["inventories"]) + sl["inventories"],
        fixed_assets=float(bA["fixed_assets"]) + sl["fixed_assets"] + writeup,
        goodwill=goodwill_total, other_assets=float(bA["other_assets"]) + sl["other_assets"],
        payables=float(bA["payables"]) + sl["payables"], debt=float(bA["borrowings"] + bB["borrowings"]),
        revolver=float(bA["revolver"] + bB["revolver"]), leases=float(bA["leases"]) + sl["leases"],
        other_liabilities=float(bA["other_liabilities"]) + sl["other_liabilities"] + dtl,
        equity_parent=float(bA["equity_parent"]) + S_stock - adv - fin_fee, nci=float(bA["minorities"] + bB["minorities"]),
        acq_debt=D_new)
    assets = (opening["cash"] + opening["receivables"] + opening["inventories"] + opening["fixed_assets"]
              + opening["goodwill"] + opening["other_assets"])
    liabs = (opening["payables"] + opening["debt"] + opening["revolver"] + opening["acq_debt"] + opening["leases"]
             + opening["other_liabilities"])
    opening_check = assets - liabs - opening["equity_parent"] - opening["nci"]

    # ── combined operating drivers, years y0+1 .. y0+5
    j = [y0 + t for t in range(1, n_years + 1)]
    gi = lambda df, row: np.array([float(df.loc[row, y]) for y in j])
    rev = gi(isA, "revenue") + keep * gi(isB, "revenue")
    prev_rev = np.concatenate([[opening["revenue"]], rev[:-1]])
    syn = d.synergies_runrate * np.array(d.synergy_phasing[:n_years])
    stepup = writeup / d.writeup_life_years
    ebit = gi(isA, "ebit") + keep * gi(isB, "ebit") + syn - stepup
    da = gi(isA, "da") + keep * gi(isB, "da") + stepup
    capex = (np.array([a_s.capex_pct[t] * float(isA.loc["revenue", y]) for t, y in enumerate(j, start=1)])
             + keep * np.array([a_b.capex_pct[t] * float(isB.loc["revenue", y]) for t, y in enumerate(j, start=1)]))
    lease = (np.array([a_s.lease_pct[t] * float(isA.loc["revenue", y]) for t, y in enumerate(j, start=1)])
             + keep * np.array([a_b.lease_pct[t] * float(isB.loc["revenue", y]) for t, y in enumerate(j, start=1)]))
    jv = gi(isA, "jv_income") + keep * gi(isB, "jv_income")
    ebit_a, ebit_b = gi(isA, "ebit"), keep * gi(isB, "ebit")
    tax_a = np.array(a_s.tax_rate[1:n_years + 1]); tax_b = np.array(a_b.tax_rate[1:n_years + 1])
    tax_pf = (tax_a * ebit_a + tax_b * ebit_b) / (ebit_a + ebit_b)
    integ_total = d.integration_cost_multiple * d.synergies_runrate
    one_off = [integ_total * 0.5, integ_total * 0.5] + [0.0] * (n_years - 2)

    dps = np.array([a_s.dividends[t] / shares_s for t in range(1, n_years + 1)])
    debt_plus_leases_a = bA["borrowings"] + bA["revolver"] + bA["leases"]
    debt_plus_leases_b = bB["borrowings"] + bB["revolver"] + keep * bB["leases"]
    rate_pf = (a_s.finance_rate * debt_plus_leases_a + a_b.finance_rate * debt_plus_leases_b) / (debt_plus_leases_a + debt_plus_leases_b)
    nci_fixed = float(a_s.nci_income_fixed + a_b.nci_income_fixed)   # hybrid coupons etc. are unaffected by the deal
    min_cash_pct = (a_s.min_cash_pct * isA.loc["revenue", y0] + a_b.min_cash_pct * keep * isB.loc["revenue", y0]) / opening["revenue"]
    rf = A["v"].risk_free
    acq_rate = rf + d.new_debt_spread

    a_pf = Assumptions(
        revenue_growth=list(rev / prev_rev - 1), ebit_margin=list(ebit / rev), da_pct=list(da / rev), capex_pct=list(capex / rev),
        lease_pct=list(lease / rev), tax_rate=list(tax_pf), jv_pct=list(jv / rev),
        dividends=list(dps * shares_pf), buybacks=[d.buyback_pct * a_s.buybacks[t] for t in range(1, n_years + 1)],
        net_debt_issuance=[0.0] * n_years, receivable_pct=opening["receivables"] / opening["revenue"],
        inventory_pct=opening["inventories"] / opening["revenue"], payable_pct=opening["payables"] / opening["revenue"],
        finance_rate=float(rate_pf), cash_rate=a_s.cash_rate, nci_share=0.0, nci_income_fixed=nci_fixed, min_cash_pct=float(min_cash_pct),
        one_off_costs=one_off, acq_debt_rate=float(acq_rate), acq_sweep_pct=d.acq_sweep_pct, label="pro forma")
    pf = forecast_from(opening, a_pf, yrs_pf[0])

    # ── standalone comparators on the same buyback policy and constant share count
    a_cmp = replace(a_s, buybacks=[d.buyback_pct * b for b in a_s.buybacks])
    cmp_out = forecast(A["h"], a_cmp)
    ni_s = np.array([float(cmp_out["income_statement"].loc["net_income_parent", y]) for y in yrs_pf])
    ni_pf = pf["income_statement"].loc["net_income_parent"].values.astype(float)
    eps_s, eps_pf = ni_s / shares_s, ni_pf / shares_pf
    one_off_at = np.array(one_off) * (1 - tax_pf)
    ppa_at = stepup * (1 - d.dtl_rate)
    adj_ni_pf = ni_pf + one_off_at + ppa_at
    acc = pd.DataFrame({"standalone_eps": eps_s, "pro_forma_eps": eps_pf, "accretion": eps_pf / eps_s - 1,
                        "adj_pro_forma_eps": adj_ni_pf / shares_pf, "adj_accretion": adj_ni_pf / shares_pf / eps_s - 1,
                        "standalone_ni": ni_s, "pro_forma_ni": ni_pf, "synergies_pre_tax": syn, "integration_costs_pre_tax": one_off,
                        "ppa_stepup_da": stepup}, index=yrs_pf).T

    # ── credit
    k = pf["kpis"]
    credit = pd.DataFrame({"net_debt": k.loc["net_debt"].values, "net_debt_to_ebitda": k.loc["net_debt_to_ebitda"].values,
                           "acquisition_debt": pf["balance_sheet"].loc["acquisition_debt"].values,
                           "interest_cover": (pf["income_statement"].loc["ebitda"] / pf["income_statement"].loc["interest_expense"]).values,
                           "dividend_cover_fcf": (k.loc["free_cash_flow"] / (-pf["cash_flow"].loc["dividends"])).values}, index=yrs_pf).T
    lev_a = float(bsA.loc[["borrowings", "revolver", "leases"], y0].sum() - bA["cash"]) / float(isA.loc["ebitda", y0])
    pf_open_nd = opening["debt"] + opening["revolver"] + opening["acq_debt"] + opening["leases"] - opening["cash"]
    pf_open_ebitda = float(isA.loc["ebitda", y0] + keep * isB.loc["ebitda", y0])
    lev_close = pf_open_nd / pf_open_ebitda

    # ── contribution analysis (year 1 after close)
    t1 = yrs_pf[0]
    fcf_a = float(cmp_out["kpis"].loc["free_cash_flow", t1]); fcf_b = float(B["out"]["kpis"].loc["free_cash_flow", t1])
    rows = {"Revenue": (isA.loc["revenue", t1], keep * isB.loc["revenue", t1]),
            "EBITDA": (isA.loc["ebitda", t1], keep * isB.loc["ebitda", t1]),
            "Net income to shareholders": (isA.loc["net_income_parent", t1], isB.loc["net_income_parent", t1]),
            "Free cash flow": (fcf_a, fcf_b),
            "Market capitalisation": (mcap_s, mcap_b)}
    contrib = pd.DataFrame({k_: dict(shell=v[0] / (v[0] + v[1]), bp=v[1] / (v[0] + v[1])) for k_, v in rows.items()}).T
    full_stock_bp = P / (P + mcap_s)

    # ── value creation
    w = A["wacc"]
    t_syn = float(np.average(tax_pf))
    flows = d.synergies_runrate * np.array(list(d.synergy_phasing) + [1.0] * (len(isA.columns) - len(d.synergy_phasing) - 1))
    # synergies run from year y0+1 to the end of the 10-year forecast, then in perpetuity without growth
    all_years = [y for y in isA.columns if y > y0]
    syn_cf = np.array([d.synergies_runrate * (d.synergy_phasing[i] if i < len(d.synergy_phasing) else 1.0) for i in range(len(all_years))])
    t_idx = np.array([y - BASE_YEAR - 0.5 for y in all_years])
    pv_syn = float((syn_cf * (1 - t_syn) / (1 + w) ** t_idx).sum() + syn_cf[-1] * (1 - t_syn) / w / (1 + w) ** (all_years[-1] - BASE_YEAR - 0.5))
    pv_int = float(sum(integ_total * 0.5 * (1 - tax_pf[i]) / (1 + w) ** (yrs_pf[i] - BASE_YEAR - 0.5) for i in range(2)))
    v_s, v_b = float(A["r"]["equity_value"]), float(B["r"]["equity_value"])
    combined_equity = v_s + v_b + pv_syn - pv_int - adv - fin_fee - C_cash + proceeds * 0   # divestment is value-neutral at FV
    shell_share_after = 1 - ownership_bp
    value_per_share_after = shell_share_after * combined_equity / shares_s
    value_per_share_before = v_s / shares_s
    premium_usd = P - mcap_b
    synergy_value_net = pv_syn - pv_int
    value = dict(
        intrinsic_before_usd=value_per_share_before, intrinsic_after_usd=value_per_share_after,
        intrinsic_accretion=value_per_share_after / value_per_share_before - 1,
        pv_synergies=pv_syn, pv_integration=pv_int, premium_usd=premium_usd, net_synergy_value=synergy_value_net,
        premium_share_of_synergies=premium_usd / pv_syn if pv_syn > 0 else np.nan,
        standalone_equity_shell=v_s, standalone_equity_bp=v_b, bp_market_cap=mcap_b, shell_market_cap=mcap_s,
        fees=adv + fin_fee, fx=fx)

    su = dict(
        uses={"Equity purchase price": P, "Advisory fees": adv, "Financing fees": fin_fee,
              **({"Surplus cash retained": surplus} if surplus > 1e-9 else {})},
        sources={"New Shell shares": S_stock, "Acquisition debt": D_new, "Cash from balance sheet": cash_used, "Divestment proceeds": proceeds},
        price_per_share_usd=px_b * (1 + d.premium), offer_gbp_pence=B["market"]["price_gbp_pence"] * (1 + d.premium),
        exchange_ratio=(px_b * (1 + d.premium) * d.pct_stock) / px_s, new_shares_m=n_new, shares_pf_m=shares_pf,
        ownership_bp=ownership_bp, ownership_shell=1 - ownership_bp, ev_target=ev_target, nd_target=nd_b)
    ppa = dict(equity_purchase_price=P, book_equity_parent=e_b, less_existing_goodwill=-gw_b_old, plus_fair_value_writeup=writeup,
               less_deferred_tax=-dtl, fair_value_net_assets=fv_net_assets, goodwill_created=goodwill_new,
               divestment_adjustment=goodwill_adj, annual_stepup_da=stepup, shell_goodwill_before=float(bA["goodwill"]),
               goodwill_total=goodwill_total)

    flags = []
    if abs(opening_check) > 1e-4:
        flags.append(f"Opening balance sheet does not balance by {opening_check:,.2f}")
    if credit.loc["net_debt_to_ebitda", yrs_pf[0]] > d.max_leverage_flag:
        flags.append(f"Pro forma leverage {credit.loc['net_debt_to_ebitda', yrs_pf[0]]:.1f}x net debt/EBITDA after year 1 (flag level {d.max_leverage_flag:.1f}x)")
    if (pf["balance_sheet"].loc["revolver"] > 1).any():
        flags.append("Revolver is drawn in the pro forma forecast: dividends and debt service exceed free cash flow")
    if value["premium_share_of_synergies"] > 1:
        flags.append("The premium paid exceeds the present value of the synergies")
    if ownership_bp > 0.5:
        flags.append("BP shareholders would own a majority of the combined company: this is a reverse takeover in substance")
    if abs(pf["balance_sheet"].loc["balance_check"]).max() > 1e-4:
        flags.append("Pro forma forecast balance sheet does not balance")

    return dict(inputs=d, su=su, ppa=ppa, opening=opening, opening_check=opening_check, pf=pf, accretion=acc, credit=credit,
                contribution=contrib, value=value, flags=flags, A=A, B=B, standalone_cmp=cmp_out,
                leverage=dict(shell_before=lev_a, pro_forma_close=lev_close), full_stock_bp=full_stock_bp, years=yrs_pf,
                shares=dict(shell=shares_s, pro_forma=shares_pf, new=n_new), prices=dict(shell_usd=px_s, bp_usd=px_b))


def sensitivity_accretion(S: Settings, d: DealInputs, rows: list[float], cols: list[float], row_attr: str, col_attr: str,
                          year_index: int = 1, metric: str | tuple = "accretion"):
    """Grid of EPS accretion (or intrinsic accretion) in the given pro forma year (0 = first year after close).
    Pass a tuple of (metric, year_index) pairs to get several grids from a single pass over the deals."""
    specs = metric if isinstance(metric, tuple) else ((metric, year_index),)
    out = {sp: {} for sp in specs}
    for r_ in rows:
        vals = {sp: [] for sp in specs}
        for c_ in cols:
            res = run_deal(S, replace(d, **{row_attr: r_, col_attr: c_}))
            for m_, yi in specs:
                vals[(m_, yi)].append(res["value"]["intrinsic_accretion"] if m_ == "intrinsic" else float(res["accretion"].loc[m_, res["years"][yi]]))
        for sp in specs:
            out[sp][r_] = vals[sp]
    grids = {sp: pd.DataFrame(out[sp], index=cols).T for sp in specs}
    return grids if isinstance(metric, tuple) else grids[specs[0]]


def breakeven_synergies(S: Settings, d: DealInputs, year_index: int = 2, lo: float = 0.0, hi: float = 20_000.0,
                        metric: str = "accretion") -> float:
    """Run-rate synergies (USD m) that make EPS accretion zero in the chosen pro forma year (default: year 3, after
    integration costs have fallen away). Integration costs scale with synergies, so early years can be unfixable."""
    def f(s_):
        res = run_deal(S, replace(d, synergies_runrate=s_))
        return float(res["accretion"].loc[metric, res["years"][year_index]])
    if f(lo) >= 0:
        return 0.0
    if f(hi) < 0:
        return float("nan")
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return (lo + hi) / 2
