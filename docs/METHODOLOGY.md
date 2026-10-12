# Methodology

How each part of the XAVI suite works, how it is checked, and what it cannot tell you.
All company figures are in US dollars (the reporting currency of Shell and BP); share values are converted to pence.

## Data

- **Company accounts.** Shell and BP file Form 20-F with the SEC in IFRS. `extract.py` pulls the XBRL facts from SEC
  EDGAR for FY2021–FY2025, keeps the latest restated value for each year, and maps the tags to model lines.
  Derived lines: D&A excluding impairments (Shell's cash-flow add-back includes them), lease principal, operating
  EBIT (excluding JV profit and non-operating finance items), decommissioning provisions and net pension deficit.
- **Segments.** `extract_segments.py` parses note 7 of Shell's FY2025 20-F (the full filing, downloaded from EDGAR
  with a contact email in the request header, as the SEC requires).
- **Market data.** Prices, the FTSE 100 benchmark, GBP/USD, the US 10-year yield and the 13-week T-bill come from
  Yahoo Finance via `yfinance`. This source is unofficial: useful and usually right, but not authoritative.
- **Quartr** was explored and is not used, because it requires a paid subscription.

## Three-statement forecast (`model/three_statement.py`)

Ten years: five explicit, five fading to terminal growth. Revenue drives margins, D&A, capex, leases, JV profit and
working capital. Interest is charged on average balances, which makes interest, cash, the revolver and buybacks
mutually dependent; the engine solves this by fixed-point iteration (the Excel version uses iterative calculation,
with a switch to fall back to opening balances). Buybacks flex down to protect a cash floor; if the floor would still
be breached, a revolver is drawn and repaid first when cash allows. Lines the model does not drive are held flat as
balancing items, so the balance sheet is exact. The same engine runs from any opening balance sheet, which is how the
merged company is forecast.

## DCF (`model/dcf.py`)

Unlevered free cash flow = operating EBIT × (1 − tax) + D&A − capex − new leases − increase in working capital.
Leases are treated as debt. Cash flows are discounted at WACC with the mid-year convention from 31 Dec 2025; the
terminal value uses perpetuity growth (an exit multiple is shown as a cross-check). Enterprise value bridges to equity
by adding JV stakes and cash, and deducting borrowings, leases, minorities and after-tax debt-like provisions. The
per-share value is rolled forward to the valuation date at the cost of equity, less interim dividends.

## Monte Carlo (`model/montecarlo.py`)

Because unlevered cash flow does not depend on financing, the simulation is fully vectorised. A commodity-cycle
shock moves revenue growth and a persistent margin shock together; capex, tax, discount-rate inputs, terminal growth
and FX are also drawn. A zero-shock path reproduces the DCF exactly (tested). Outputs: the value distribution,
probability of exceeding the market price, a one-at-a-time tornado and rank correlations.

## Carve-out LBO (`model/lbo.py`, `model/segments.py`)

A cash-free, debt-free purchase of one Shell division at a multiple of LTM EBITDA, funded by a term loan B, senior
notes, a PIK mezzanine and sponsor equity, with an undrawn revolver. The model runs a 100% cash sweep, interest on
average balances, a deductibility cap and a standalone-cost drag. It returns IRR, money multiple, a value-creation
bridge, the maximum entry price for a target return and the margin cushion before the equity is lost. Structures
that run out of cash are flagged "not financeable" and their returns are shown as not meaningful.

## Merger (`model/ma.py`)

Shell acquires BP at a premium, part in new shares and part in cash funded by an acquisition loan. IFRS 3 purchase
accounting builds the combined opening balance sheet (fair-value uplift, deferred tax, goodwill, optional
divestments). The combined company is then forecast with the same engine: combined operating lines, phased
synergies, integration costs, the PPA depreciation, both companies' existing debt and the new loan, swept with excess
cash. Outputs: EPS accretion (reported and adjusted), contribution analysis, leverage, breakeven synergies, and two
value tests (premium against the present value of synergies; DCF value per Shell share with and without the deal).

## Portfolio (`model/portfolio.py`)

Prices are converted to sterling (or kept in local currency for a hedged view). Weekly returns drive a Ledoit-Wolf
covariance and expected returns that blend history with a CAPM prior. Long-only optimisers: maximum Sharpe, minimum
variance, risk parity, maximum diversification, and equal weight. Risk: historical and normal VaR/CVaR, drawdowns,
stress tests and risk contributions. A walk-forward backtest re-estimates on the previous two years only. A Student-t
simulation projects a range of outcomes.

## Verification

- **Tests:** 87 automated tests (`py -3.12 -m pytest -q`) covering accounting identities, monotonicity, solver
  correctness, no look-ahead in the backtest, and regressions for bugs found along the way.
- **Audit:** `audit.py` re-runs 86 integrity checks across the data, every model and the Excel workbook, and writes
  `output/audit_report.md`.
- **Independent rebuild:** the Excel workbook re-implements the forecast, DCF, LBO, merger terms and portfolio
  maths as live formulas; Excel's results match the Python engine to within about 1e-9 on 36 reconciliation lines.

## Limitations

- Results are driven by judgement-based defaults (see `ASSUMPTIONS.md`), not by a view on any company.
- No explicit oil and gas price model; the commodity cycle enters only through growth and margin shocks.
- Only five annual observations: volatilities and scenario widths cannot be estimated statistically.
- The DCF disagrees with the market on both companies (Shell lower, BP higher), and the merger value test inherits
  that disagreement.
- Segment working capital, separation tax costs, competition remedies, covenant packages, stamp duty and tax
  wrappers are simplified or omitted.
- Market data is unofficial; BP's share count is not cross-checked to its filing.
- Not investment advice.
