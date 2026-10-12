"""Carve-out leveraged buyout model.

Structure: cash-free/debt-free purchase of a division at an EV/EBITDA multiple; funded by a term loan B, senior notes,
a PIK-toggle mezzanine and sponsor equity, with an undrawn revolver. 100% excess-cash sweep to the term loan, interest
on average balances (circularity solved by fixed-point iteration), interest-deductibility cap, standalone-cost drag,
exit at a multiple of year-H EBITDA.

Everything is annual and in USD millions. Entry/exit multiples are applied to reported (IFRS) EBITDA; lenders and the
projections use pro-forma EBITDA after standalone costs.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
import numpy as np
import pandas as pd

N_PROJ = 7


@dataclass
class LBOInputs:
    # operating base (USD m)
    revenue0: float
    ltm_ebitda: float
    revenue_growth: list[float]
    ebitda_margin: list[float]           # before standalone costs
    da_pct: float
    capex_pct: float
    nwc_pct: float
    standalone_cost_pct: float = 0.004   # of revenue; costs previously absorbed by the parent
    tax_rate: float = 0.28
    interest_cap_pct_ebitda: float | None = 0.30   # deductibility cap on net interest (None = uncapped)
    # deal
    entry_multiple: float = 7.5
    exit_multiple: float | None = None   # None -> same as entry multiple
    hold_years: int = 5
    advisory_fee_pct: float = 0.010      # of EV
    separation_cost_pct: float = 0.010   # of EV, one-off (TSA, IT, rebranding)
    exit_cost_pct: float = 0.010         # of exit EV
    min_cash_pct_revenue: float = 0.010
    # financing, in turns of pro-forma EBITDA
    tlb_x: float = 3.0
    notes_x: float = 1.5
    mezz_x: float = 0.5
    base_rate: float = 0.04
    tlb_spread: float = 0.035
    notes_coupon: float = 0.075
    mezz_cash: float = 0.08
    mezz_pik: float = 0.03
    revolver_commit_x: float = 0.75      # revolver commitment in turns of pro-forma EBITDA
    revolver_spread: float = 0.030
    undrawn_fee: float = 0.005
    tlb_amort_pct: float = 0.01
    sweep_pct: float = 1.0
    financing_fee_pct: float = 0.0225    # of funded debt; amortised over 7 years
    fee_amort_years: int = 7
    mgmt_promote_pct: float = 0.0        # share of equity gain paid to management
    max_ltv: float = 0.70                # total debt capped at this share of purchase EV (tranches scaled pro rata)
    label: str = "base"

    @property
    def exit_mult(self) -> float:
        return self.entry_multiple if self.exit_multiple is None else self.exit_multiple

    @property
    def pf_ebitda0(self) -> float:
        return self.ltm_ebitda - self.revenue0 * self.standalone_cost_pct


def sources_uses(i: LBOInputs) -> dict:
    ev = i.entry_multiple * i.ltm_ebitda
    pf = i.pf_ebitda0
    tlb, notes, mezz = i.tlb_x * pf, i.notes_x * pf, i.mezz_x * pf
    scale = min(1.0, i.max_ltv * ev / (tlb + notes + mezz)) if (tlb + notes + mezz) > 0 else 1.0
    tlb, notes, mezz = tlb * scale, notes * scale, mezz * scale
    debt = tlb + notes + mezz
    revolver_commit = i.revolver_commit_x * pf
    fin_fees = i.financing_fee_pct * debt + 0.01 * revolver_commit
    adv, sep = i.advisory_fee_pct * ev, i.separation_cost_pct * ev
    min_cash = i.min_cash_pct_revenue * i.revenue0
    uses = dict(purchase_price=ev, advisory_fees=adv, financing_fees=fin_fees, separation_costs=sep, cash_to_balance_sheet=min_cash)
    total_uses = sum(uses.values())
    equity = total_uses - debt
    src = dict(term_loan_b=tlb, senior_notes=notes, mezzanine=mezz, revolver_drawn=0.0, sponsor_equity=equity)
    return dict(uses=uses, sources=src, total=total_uses, ev=ev, debt=debt, equity=equity, pf_ebitda=pf,
                revolver_commit=revolver_commit, fin_fees=fin_fees, min_cash=min_cash)


def run(i: LBOInputs) -> dict:
    su = sources_uses(i)
    n = N_PROJ
    assert len(i.revenue_growth) >= n and len(i.ebitda_margin) >= n
    cash_yield = max(i.base_rate - 0.005, 0.0)
    tlb0, notes, mezz0 = su["sources"]["term_loan_b"], su["sources"]["senior_notes"], su["sources"]["mezzanine"]
    rcf_commit = su["revolver_commit"]
    fee_amort = su["fin_fees"] / i.fee_amort_years

    rev_prev = i.revenue0
    cash, rcf, tlb, mezz = su["min_cash"], 0.0, tlb0, mezz0
    rows, flags = [], []
    for t in range(1, n + 1):
        rev = rev_prev * (1 + i.revenue_growth[t - 1])
        ebitda = rev * (i.ebitda_margin[t - 1] - i.standalone_cost_pct)
        da, capex = rev * i.da_pct, rev * i.capex_pct
        dnwc = i.nwc_pct * (rev - rev_prev)
        ebit = ebitda - da
        min_cash = i.min_cash_pct_revenue * rev
        mand = min(tlb, i.tlb_amort_pct * tlb0)

        draw = repay = sweep = 0.0
        tlb_end, rcf_end, cash_end = tlb, rcf, cash
        for _ in range(300):
            rcf_avg, tlb_avg, cash_avg = (rcf + rcf_end) / 2, (tlb + tlb_end) / 2, (cash + cash_end) / 2
            int_rcf = (i.base_rate + i.revolver_spread) * rcf_avg + i.undrawn_fee * max(rcf_commit - rcf_avg, 0)
            int_tlb = (i.base_rate + i.tlb_spread) * tlb_avg
            int_notes = i.notes_coupon * notes
            int_mezz_cash = i.mezz_cash * mezz
            pik = i.mezz_pik * mezz
            int_income = cash_yield * cash_avg
            cash_interest = int_rcf + int_tlb + int_notes + int_mezz_cash - int_income
            gross_interest = int_rcf + int_tlb + int_notes + int_mezz_cash + pik + fee_amort
            net_interest = gross_interest - int_income
            deductible = net_interest if i.interest_cap_pct_ebitda is None else min(net_interest, max(i.interest_cap_pct_ebitda * ebitda, 0))
            taxable = max(ebit - deductible, 0.0)
            tax = i.tax_rate * taxable
            cfads = ebitda - tax - capex - dnwc
            avail = cash + cfads - cash_interest - mand - min_cash
            new_draw = min(max(-avail, 0.0), max(rcf_commit - rcf, 0.0))
            new_repay = min(rcf, max(avail, 0.0))
            sweep_cap = max(avail - new_repay, 0.0)
            new_sweep = i.sweep_pct * min(tlb - mand, sweep_cap)
            new_tlb = tlb - mand - new_sweep
            new_rcf = rcf + new_draw - new_repay
            new_cash = cash + cfads - cash_interest - mand + new_draw - new_repay - new_sweep
            done = max(abs(new_tlb - tlb_end), abs(new_rcf - rcf_end), abs(new_cash - cash_end)) < 1e-7
            tlb_end, rcf_end, cash_end, draw, repay, sweep = new_tlb, new_rcf, new_cash, new_draw, new_repay, new_sweep
            if done:
                break
        mezz_end = mezz + pik
        net_income = ebit - net_interest - tax
        total_debt = tlb_end + notes + mezz_end + rcf_end
        senior = tlb_end + rcf_end
        if cash_end < min_cash - 1e-6:
            flags.append(f"Year {t}: liquidity shortfall of ${min_cash - cash_end:,.0f}m — revolver exhausted")
        rows.append(dict(year=t, revenue=rev, ebitda=ebitda, da=da, ebit=ebit, capex=capex, change_nwc=dnwc, tax=tax,
                         cfads=cfads, cash_interest=cash_interest, gross_interest=gross_interest, deductible_interest=deductible,
                         mandatory_amort=mand, sweep=sweep, revolver_draw=draw, revolver_repay=repay, pik=pik,
                         net_income=net_income, cash=cash_end, revolver=rcf_end, term_loan_b=tlb_end, senior_notes=notes,
                         mezzanine=mezz_end, total_debt=total_debt, net_debt=total_debt - cash_end,
                         debt_to_ebitda=total_debt / ebitda if ebitda > 0 else np.nan,
                         senior_to_ebitda=senior / ebitda if ebitda > 0 else np.nan,
                         net_debt_to_ebitda=(total_debt - cash_end) / ebitda if ebitda > 0 else np.nan,
                         interest_cover=ebitda / cash_interest if cash_interest > 0 else np.nan,
                         capex_cover=(ebitda - capex) / cash_interest if cash_interest > 0 else np.nan,
                         fcf=cfads - cash_interest))
        rev_prev, cash, rcf, tlb, mezz = rev, cash_end, rcf_end, tlb_end, mezz_end

    df = pd.DataFrame(rows).set_index("year").T
    ret = returns(i, su, df)
    if i.hold_years > 0 and ret["moic"] < 1.0:
        flags.append("Sponsor loses capital at the chosen exit")
    if su["sources"]["sponsor_equity"] <= 0:
        flags.append("Debt exceeds total uses — equity cheque is non-positive")
    if su["ev"] > 0 and su["debt"] / su["total"] > 0.70:
        flags.append(f"Debt is {su['debt'] / su['total'] * 100:.0f}% of the capital structure — above typical lending limits")
    if df.loc["ebitda"].min() <= 0:
        flags.append("EBITDA turns non-positive in the projection")
    horizon = df.loc[:, 1: i.hold_years]
    weak = horizon.loc["interest_cover"].dropna()
    if len(weak) and weak.min() < 1.5:
        flags.append(f"EBITDA covers cash interest only {weak.min():.1f}x at the weakest point (lenders typically want 2x+)")
    if (horizon.loc["capex_cover"].dropna() < 1.0).any():
        flags.append("(EBITDA - capex) does not cover cash interest in at least one year")
    financeable = not any("liquidity shortfall" in f for f in flags[:n])
    return dict(inputs=i, su=su, projections=df, returns=ret, flags=flags, financeable=financeable)


def returns(i: LBOInputs, su: dict, df: pd.DataFrame, hold: int | None = None) -> dict:
    h = i.hold_years if hold is None else hold
    col = df[h]
    ev_exit = i.exit_mult * col["ebitda"]
    net_debt_exit = col["net_debt"]
    exit_costs = i.exit_cost_pct * ev_exit
    equity_pre = ev_exit - net_debt_exit - exit_costs
    equity_in = su["equity"]
    gain = equity_pre - equity_in
    promote = max(gain, 0) * i.mgmt_promote_pct
    equity_exit = equity_pre - promote
    moic = equity_exit / equity_in if equity_in > 0 else np.nan
    irr = moic ** (1 / h) - 1 if moic and moic > 0 else (-1.0 if equity_in > 0 else np.nan)

    pf0 = su["pf_ebitda"]
    m0 = su["ev"] / pf0
    nd0 = su["debt"] - su["min_cash"]
    fees = su["uses"]["advisory_fees"] + su["uses"]["financing_fees"] + su["uses"]["separation_costs"]
    bridge = {
        "EBITDA growth": (col["ebitda"] - pf0) * m0,
        "Multiple & separation drag": (i.exit_mult - m0) * col["ebitda"],
        "Net debt reduction": nd0 - net_debt_exit,
        "Fees & costs": -(fees + exit_costs),
        "Management promote": -promote,
    }
    return dict(hold=h, ev_exit=ev_exit, net_debt_exit=net_debt_exit, exit_costs=exit_costs, equity_in=equity_in,
                equity_exit=equity_exit, moic=moic, irr=irr, bridge=bridge, entry_multiple_on_pf=m0,
                bridge_check=equity_exit - equity_in - sum(bridge.values()))


def irr_by_exit_year(i: LBOInputs, res: dict | None = None) -> pd.DataFrame:
    res = run(i) if res is None else res
    rows = [dict(exit_year=h, **{k: returns(i, res["su"], res["projections"], h)[k] for k in ("irr", "moic", "equity_exit")})
            for h in range(2, N_PROJ + 1)]
    return pd.DataFrame(rows).set_index("exit_year")


def sensitivity_irr(i: LBOInputs, entry_multiples: list[float], exit_multiples: list[float]) -> pd.DataFrame:
    rows = {}
    for en in entry_multiples:
        rows[en] = [run(replace(i, entry_multiple=en, exit_multiple=ex))["returns"]["irr"] for ex in exit_multiples]
    df = pd.DataFrame(rows, index=exit_multiples).T
    df.index = [f"{x:g}x" for x in df.index]
    df.columns = [f"{x:g}x" for x in df.columns]
    return df.rename_axis("Entry")


def sensitivity_leverage(i: LBOInputs, tlb_turns: list[float], exit_multiples: list[float]) -> pd.DataFrame:
    rows = {}
    for x in tlb_turns:
        rows[x] = [run(replace(i, tlb_x=x, exit_multiple=ex))["returns"]["irr"] for ex in exit_multiples]
    df = pd.DataFrame(rows, index=exit_multiples).T
    df.index = [f"{x + i.notes_x + i.mezz_x:g}x total" for x in df.index]
    df.columns = [f"{x:g}x" for x in df.columns]
    return df.rename_axis("Leverage")


def max_entry_multiple(i: LBOInputs, target_irr: float, lo: float = 2.0, hi: float = 25.0, hold_exit_equals_entry: bool = False) -> float:
    """Highest entry multiple that still delivers `target_irr`, holding the exit multiple and debt (in turns of EBITDA)."""
    def f(m):
        j = replace(i, entry_multiple=m, exit_multiple=m if hold_exit_equals_entry else i.exit_mult)
        return run(j)["returns"]["irr"] - target_irr
    flo, fhi = f(lo), f(hi)
    if np.isnan(flo) or flo < 0:
        return float("nan")
    if fhi > 0:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def breakeven_margin_shock(i: LBOInputs, target_irr: float = 0.0) -> float:
    """EBITDA-margin reduction (in percentage points of revenue, all years) at which IRR falls to `target_irr`."""
    def f(shock):
        j = replace(i, ebitda_margin=[m - shock for m in i.ebitda_margin])
        return run(j)["returns"]["irr"] - target_irr
    if f(0.0) < 0:
        return 0.0
    lo, hi = 0.0, 0.10
    if f(hi) > 0:
        return hi
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    return (lo + hi) / 2
