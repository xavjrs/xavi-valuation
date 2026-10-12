"""Integrated 3-statement forecast (annual, USD m), 10 years: 5 explicit + 5 fade.

Design notes
- History comes from data/clean/<company>_annual.csv (SEC 20-F, IFRS).
- EBIT is *operating* EBIT: it excludes share of associates/JVs and non-operating finance items. JV profit is
  forecast separately (post-tax, assumed fully distributed) and the JV stake is valued at book in the equity bridge.
- Lines the forecast does not drive (derivatives, deferred tax, provisions, ...) are folded into `other_assets` /
  `other_liabilities`, derived as base-year plugs and held flat, so the balance sheet is exact without inventing detail.
- IFRS 16 leases are treated as debt. New leases are assumed equal to principal repaid (flat liability); the new
  right-of-use assets are non-cash investment and the principal is a financing outflow.
- Cash policy: buybacks flex to protect a cash floor; if the floor would be breached a revolver is drawn, and it is
  repaid ahead of buybacks when cash allows.
- Interest runs on average balances; the interest <-> cash <-> buyback circularity is solved by fixed-point iteration.
- Calibration is generic (from each company's own history) so the same code values Shell and BP.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

BASE_YEAR = 2025
N_EXPLICIT = 5
N_YEARS = 10


@dataclass
class Assumptions:
    revenue_growth: list[float]
    ebit_margin: list[float]
    da_pct: list[float]             # underlying D&A (excl. impairments) as % of revenue
    capex_pct: list[float]
    lease_pct: list[float]          # new leases = principal repaid, % of revenue
    tax_rate: list[float]
    jv_pct: list[float]             # post-tax share of JV/associate profit, % of revenue (fully distributed)
    dividends: list[float]          # USD m, to parent shareholders
    buybacks: list[float]           # USD m target; flexes down to protect the cash floor
    net_debt_issuance: list[float]  # USD m, + = new borrowing
    receivable_pct: float
    inventory_pct: float
    payable_pct: float
    finance_rate: float             # on average borrowings + leases
    cash_rate: float                # on average cash
    nci_share: float                # share of net income attributable to minorities (paid out in cash)
    label: str = "base"
    min_cash_pct: float = 0.09      # cash floor as % of revenue
    terminal_growth: float = 0.015
    # M&A extensions (all inactive by default)
    one_off_costs: list[float] | None = None   # USD m pre-tax, below EBIT (e.g. integration costs), tax-deductible
    acq_debt_rate: float = 0.0                 # rate on the acquisition-debt tranche in the opening balance sheet
    acq_sweep_pct: float = 1.0                 # share of excess cash used to repay acquisition debt before buybacks
    nci_income_fixed: float | None = None      # USD m a year to minorities (e.g. hybrid coupons); overrides nci_share


SCENARIOS = {  # shifts to growth / margin over the explicit period, mean-reverting to zero by year 10
    "bear": dict(growth=-0.03, margin=-0.02),
    "base": dict(growth=0.0, margin=0.0),
    "bull": dict(growth=+0.03, margin=+0.02),
}


def load_history(company: str) -> pd.DataFrame:
    df = pd.read_csv(f"data/clean/{company}_annual.csv", index_col=0)
    df.columns = [int(c) for c in df.columns]
    return df


def hist_metrics(h: pd.DataFrame, cash_rate: float = 0.03) -> pd.DataFrame:
    """Per-year ratios used for calibration and shown in the dashboard."""
    r = h.loc["revenue"]
    m = pd.DataFrame({
        "revenue_growth": r.pct_change(),
        "ebit_margin": h.loc["ebit_ops"] / r,
        "ebit_margin_ex_impairment": (h.loc["ebit_ops"] + h.loc["impairment_net"]) / r,
        "tax_rate_ex_impairment": h.loc["tax"] / (h.loc["pbt"] - h.loc["jv_share"] + h.loc["impairment_net"]),
        "da_pct": h.loc["da_underlying"] / r,
        "capex_pct": h.loc["capex"] / r,
        "lease_pct": h.loc["lease_principal"] / r,
        "jv_pct": h.loc["jv_share"] / r,
    })
    return m.T


def derive_base(h: pd.DataFrame, year: int = BASE_YEAR) -> dict:
    g = lambda k: float(h.loc[k, year])
    debt = g("debt_current") + g("debt_long")
    fixed = g("ppe") + g("intangibles")
    other_assets = g("total_assets") - g("cash") - g("receivables") - g("inventories") - fixed - g("goodwill")
    other_liab = g("total_liabilities") - g("payables") - debt - g("lease_liabilities")
    return dict(revenue=g("revenue"), cash=g("cash"), receivables=g("receivables"), inventories=g("inventories"),
                fixed_assets=fixed, goodwill=g("goodwill"), other_assets=other_assets,
                payables=g("payables"), debt=debt, revolver=0.0, leases=g("lease_liabilities"),
                other_liabilities=other_liab, equity_parent=g("equity_parent"), nci=g("nci"))


def _fade(explicit: list[float], target: float, n_total: int = N_YEARS) -> list[float]:
    """Linear glide from the last explicit value to `target` over the remaining years."""
    k = n_total - len(explicit)
    last = explicit[-1]
    return list(explicit) + [last + (target - last) * (j + 1) / k for j in range(k)]


def default_assumptions(h: pd.DataFrame, scenario: str = "base", terminal_growth: float = 0.015,
                        impairment_allowance: float = 0.01,
                        near_term_growth: tuple = (-0.01, 0.01, 0.02, 0.02, 0.02)) -> Assumptions:
    s = SCENARIOS[scenario]
    y = BASE_YEAR
    g = lambda k: float(h.loc[k, y])
    hm = hist_metrics(h)
    recent = [y - 2, y - 1, y]
    norm_margin = float(hm.loc["ebit_margin_ex_impairment", recent].mean()) - impairment_allowance
    tax0 = float(hm.loc["tax_rate_ex_impairment", recent].mean())
    jv0 = float(hm.loc["jv_pct", recent].mean())
    debt_plus_leases = g("debt_current") + g("debt_long") + g("lease_liabilities")

    def shifted(base_path, shift):  # scenario shift: full over the explicit years, mean-reverting to 0 by year 10
        w = [1.0] * N_EXPLICIT + [1 - (j + 1) / (N_YEARS - N_EXPLICIT) for j in range(N_YEARS - N_EXPLICIT)]
        return [b + shift * wi for b, wi in zip(base_path, w)]

    growth = shifted(_fade(list(near_term_growth), terminal_growth), s["growth"])
    margin = shifted([norm_margin] * N_YEARS, s["margin"])
    tax = [tax0 - 0.025 * (j / (N_YEARS - 1)) for j in range(N_YEARS)]
    div0 = g("dividends_paid")
    div_g = [0.04] * N_EXPLICIT + [0.025] * (N_YEARS - N_EXPLICIT)
    dividends = list(div0 * np.cumprod([1 + x for x in div_g]))
    return Assumptions(
        revenue_growth=growth, ebit_margin=margin,
        da_pct=[g("da_underlying") / g("revenue")] * N_YEARS,
        capex_pct=[g("capex") / g("revenue")] * N_YEARS,
        lease_pct=[g("lease_principal") / g("revenue")] * N_YEARS,
        tax_rate=tax, jv_pct=[jv0] * N_YEARS,
        dividends=dividends, buybacks=[g("buybacks")] * N_YEARS, net_debt_issuance=[0.0] * N_YEARS,
        receivable_pct=g("receivables") / g("revenue"), inventory_pct=g("inventories") / g("revenue"),
        payable_pct=g("payables") / g("revenue"),
        finance_rate=g("finance_costs") / debt_plus_leases, cash_rate=0.03,
        nci_share=(g("net_income") - g("net_income_parent")) / g("net_income"),
        # minorities are largely fixed-coupon hybrids, so model a dollar amount (3-year average), not a % of profit
        nci_income_fixed=float((h.loc["net_income", recent] - h.loc["net_income_parent", recent]).mean()),
        label=scenario, terminal_growth=terminal_growth,
    )


def forecast(h: pd.DataFrame, a: Assumptions) -> dict[str, pd.DataFrame]:
    return forecast_from(derive_base(h), a, BASE_YEAR + 1)


def forecast_from(prior: dict, a: Assumptions, first_year: int) -> dict[str, pd.DataFrame]:
    """Run the forecast from any opening balance sheet (`prior`), for as many years as `a` provides."""
    prior = dict(prior)
    prior.setdefault("acq_debt", 0.0)
    n_years = len(a.revenue_growth)
    years = list(range(first_year, first_year + n_years))
    ma = prior["acq_debt"] > 0 or a.one_off_costs is not None   # show M&A rows only when relevant
    IS, BS, CF, KP = [], [], [], []

    for i, yr in enumerate(years):
        rev = prior["revenue"] * (1 + a.revenue_growth[i])
        ebit = rev * a.ebit_margin[i]
        da = rev * a.da_pct[i]
        capex = rev * a.capex_pct[i]
        lease_add = rev * a.lease_pct[i]
        jv_inc = rev * a.jv_pct[i]
        recv, inv, pay = rev * a.receivable_pct, rev * a.inventory_pct, rev * a.payable_pct
        d_nwc = (recv - prior["receivables"]) + (inv - prior["inventories"]) - (pay - prior["payables"])
        leases = prior["leases"]
        div = a.dividends[i]
        min_cash = rev * a.min_cash_pct
        one_off = a.one_off_costs[i] if a.one_off_costs is not None else 0.0

        cash, draw, repay, acq_repay = prior["cash"], 0.0, 0.0, 0.0
        for _ in range(200):  # solve the interest <-> cash <-> buyback/revolver/acquisition-debt circularity
            debt_end = prior["debt"] + prior["revolver"] + a.net_debt_issuance[i] + draw - repay
            acq_end = prior["acq_debt"] - acq_repay
            int_acq = a.acq_debt_rate * (prior["acq_debt"] + acq_end) / 2
            int_exp = a.finance_rate * ((prior["debt"] + prior["revolver"] + debt_end) / 2 + leases) + int_acq
            int_inc = a.cash_rate * (prior["cash"] + cash) / 2
            pbt_ex_jv = ebit - one_off - int_exp + int_inc
            tax = pbt_ex_jv * a.tax_rate[i]
            ni = pbt_ex_jv - tax + jv_inc
            ni_nci = a.nci_income_fixed if a.nci_income_fixed is not None else ni * a.nci_share
            cfo = ni + da - d_nwc                      # JV income is received in cash (100% payout)
            cfi = -capex
            pre = prior["cash"] + cfo + cfi + a.net_debt_issuance[i] - div - ni_nci - lease_add
            avail = pre - min_cash
            new_draw = max(0.0, -avail)
            new_repay = min(prior["revolver"], max(0.0, avail))
            new_acq = min(prior["acq_debt"], a.acq_sweep_pct * max(0.0, avail - new_repay))
            bb = max(0.0, min(a.buybacks[i], avail - new_repay - new_acq))
            cff = a.net_debt_issuance[i] + new_draw - new_repay - new_acq - div - bb - ni_nci - lease_add
            new_cash = prior["cash"] + cfo + cfi + cff
            done = (abs(new_cash - cash) < 1e-9 and abs(new_draw - draw) < 1e-9 and abs(new_repay - repay) < 1e-9
                    and abs(new_acq - acq_repay) < 1e-9)
            cash, draw, repay, acq_repay = new_cash, new_draw, new_repay, new_acq
            if done:
                break

        revolver = prior["revolver"] + draw - repay
        acq_debt = prior["acq_debt"] - acq_repay
        debt = prior["debt"] + a.net_debt_issuance[i]
        fixed = prior["fixed_assets"] + capex + lease_add - da
        eq_parent = prior["equity_parent"] + (ni - ni_nci) - div - bb
        nci = prior["nci"]
        assets = cash + recv + inv + fixed + prior["goodwill"] + prior["other_assets"]
        liabs = pay + debt + revolver + acq_debt + leases + prior["other_liabilities"]
        equity = eq_parent + nci

        is_row = dict(year=yr, revenue=rev, ebitda=ebit + da, da=da, ebit=ebit, interest_expense=int_exp,
                      interest_income=int_inc, pbt_ex_jv=pbt_ex_jv, tax=tax, jv_income=jv_inc,
                      net_income=ni, net_income_minorities=ni_nci, net_income_parent=ni - ni_nci)
        if ma:
            is_row.update(one_off_costs=one_off, interest_on_acquisition_debt=int_acq)
        IS.append(is_row)
        bs_row = dict(year=yr, cash=cash, receivables=recv, inventories=inv, fixed_assets=fixed,
                      goodwill=prior["goodwill"], other_assets=prior["other_assets"], total_assets=assets,
                      payables=pay, borrowings=debt, revolver=revolver, leases=leases,
                      other_liabilities=prior["other_liabilities"], total_liabilities=liabs,
                      equity_parent=eq_parent, minorities=nci, total_equity=equity,
                      balance_check=assets - liabs - equity)
        if ma:
            bs_row["acquisition_debt"] = acq_debt
        BS.append(bs_row)
        cf_row = dict(year=yr, net_income=ni, da=da, change_in_nwc=-d_nwc, cfo=cfo, capex=-capex, cfi=cfi,
                      net_debt_issuance=a.net_debt_issuance[i], revolver_draw_repay=draw - repay,
                      dividends=-div, buybacks=-bb, minority_distributions=-ni_nci, lease_principal=-lease_add,
                      cff=cff, net_change_in_cash=cfo + cfi + cff, closing_cash=cash)
        if ma:
            cf_row["acquisition_debt_repayment"] = -acq_repay
        CF.append(cf_row)
        ufcf = ebit * (1 - a.tax_rate[i]) + da - capex - lease_add - d_nwc  # leases as debt: ROU additions = investment
        nd = debt + revolver + acq_debt + leases - cash
        KP.append(dict(year=yr, revenue_growth=a.revenue_growth[i], ebit_margin=a.ebit_margin[i],
                       free_cash_flow=cfo - capex - lease_add, unlevered_fcf=ufcf, net_debt=nd,
                       net_debt_to_ebitda=nd / (ebit + da)))

        prior.update(revenue=rev, cash=cash, receivables=recv, inventories=inv, fixed_assets=fixed,
                     payables=pay, debt=debt, revolver=revolver, acq_debt=acq_debt, leases=leases,
                     equity_parent=eq_parent, nci=nci)

    t = lambda rows: pd.DataFrame(rows).set_index("year").T
    return dict(income_statement=t(IS), balance_sheet=t(BS), cash_flow=t(CF), kpis=t(KP))
