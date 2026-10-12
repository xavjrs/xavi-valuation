# Assumptions log

Every judgement the models rely on, its default, where it comes from, and where to change it. Values are the
defaults at the time of writing (market data as of 12 Oct 2026). **Calibrated** means derived from the company's
own reported history; **judgement** means chosen by the modeller and worth challenging.

Change points: **Sidebar** = dashboard sidebar; **Tab** = controls on that dashboard tab; **Inputs** = blue cells in
`output/XAVI_valuation_model.xlsx`; **Code** = the named Python file.

## 1. Operating forecast (3-statement)

| Assumption | Shell | BP | Basis | Type | Change in |
|---|---|---|---|---|---|
| Revenue growth, years 1–5 | −1%, +1%, +2%, +2%, +2% | same | Neutral macro placeholder, no oil-price view | Judgement | Sidebar (± adjustment), Inputs, `three_statement.py` |
| Revenue growth, years 6–10 | Linear fade to terminal growth (1.5%) | same | Convention | Judgement | Sidebar (terminal growth) |
| Operating EBIT margin | 10.9% | 10.0% | 2023–25 average excluding impairments, less a 1% recurring impairment allowance | Calibrated + judgement | Sidebar (margin adjustment, impairment allowance) |
| Scenario shifts (bear / bull) | Growth ±3pp, margin ±2pp over years 1–5, fading to zero by year 10 | same | Illustrative | Judgement | `three_statement.py` (SCENARIOS) |
| D&A, % revenue | 8.3% | 9.3% | FY2025, impairments removed | Calibrated | Inputs |
| Capex, % revenue | 7.1% | 6.9% | FY2025 | Calibrated | Inputs |
| New leases = lease principal, % revenue | 2.0% | 1.6% | FY2025 | Calibrated | Inputs |
| Tax rate on pre-tax profit ex JV | 38.4% fading to 35.9% | 41.2% fading to 38.7% | 2023–25 effective rate ex impairments, less 2.5pp over 10 years | Calibrated + judgement | Inputs |
| Share of JV profit, % revenue | 0.95% | 0.59% | 2023–25 average, fully paid out in cash | Calibrated | Inputs |
| Working capital ratios | FY2025 receivables, inventories, payables / revenue | same | FY2025 | Calibrated | Inputs |
| Interest rate on debt + leases | 4.5% | 7.0% | FY2025 finance costs / year-end debt. BP's includes unwinding of provisions, so it overstates its borrowing cost | Calibrated (BP caveat) | Inputs |
| Interest on cash | 3.0% | 3.0% | Round number below current short rates | Judgement | Inputs |
| Minority (NCI) income | $329m a year | $910m a year | 2023–25 average, as a fixed amount (BP's minorities are mostly fixed-coupon hybrid bonds) | Calibrated | Inputs |
| Dividends | FY2025 +4% a year to 2030, +2.5% after | same rule | Progressive-dividend convention | Judgement | Inputs |
| Buyback target | $13.9bn a year | $4.5bn a year | FY2025 level; flexes down to protect the cash floor | Calibrated | Inputs |
| Cash floor | 9% of revenue | same | Approximate FY2025 cash/revenue | Judgement | `three_statement.py` |
| Lines not forecast | Held flat as "other assets / other liabilities" | same | Keeps the balance sheet exact without inventing detail | Simplification | n/a |

## 2. Valuation (DCF)

| Assumption | Default | Basis | Type | Change in |
|---|---|---|---|---|
| Risk-free rate | 4.82% | Blend of the US 10-year spot (5.24%, a 5-year high) and its 1-year average (4.40%), Yahoo Finance ^TNX | Market + judgement | Sidebar (blend / spot / 1y) |
| Equity risk premium | 5.0% | Convention | Judgement | Sidebar |
| Beta | Shell 0.97, BP 0.94 | 5-year weekly regression on the FTSE 100, Blume-adjusted | Calibrated | Inputs |
| Credit spread | 0.9% | Investment-grade major | Judgement | Inputs |
| Tax shield on interest and provisions | 25% | Marginal rate, not the higher upstream effective rate | Judgement | Inputs |
| Capital structure | Market equity + book debt and leases | Market prices, 20-F | Market | n/a |
| Resulting WACC | Shell 8.25%, BP 7.56% | | Derived | |
| Terminal growth | 1.5% | Below long-run nominal GDP for a mature energy company | Judgement | Sidebar |
| Exit multiple (cross-check only) | 5.0x EBITDA | Rough sector level; not sourced from peers | Judgement | Sidebar |
| Debt-like items | Decommissioning provisions and pension deficit deducted after tax | Prudence; switchable | Judgement | Sidebar toggle |
| JV stakes | Added at book value | Simplification | Judgement | n/a |
| Valuation date | 10 Oct 2026 | Value struck at 31 Dec 2025 and rolled forward at the cost of equity less interim dividends | Convention | `dcf.py` (ValuationInputs) |

## 3. Monte Carlo

| Assumption | Default | Basis | Type |
|---|---|---|---|
| Revenue-growth shock | σ 5pp a year, independent each year | Judgement: only five annual observations exist | Judgement |
| Margin shock | σ 1.6pp, persistence 0.75 | Judgement | Judgement |
| Growth–margin correlation | 0.6 | Stands in for the commodity cycle | Judgement |
| Capex / tax level shocks | σ 0.4pp / 2pp | Judgement | Judgement |
| Discount-rate shocks | Risk-free σ 0.6pp, beta σ 0.12, ERP σ 0.7pp | Judgement | Judgement |
| Terminal growth | Triangular 0.5% / 1.5% / 2.5% | Judgement | Judgement |
| GBP/USD | Lognormal σ 7% | Judgement | Judgement |
| Paths / seed | 10,000 / 7 | Reproducible | Sidebar |

## 4. Carve-out LBO (Shell divisions)

| Assumption | Default | Basis | Type | Change in |
|---|---|---|---|---|
| Division financials | FY2023–25, Shell 20-F note 7 | Reported; validated to group accounts | Data | n/a |
| Entry multiple | 7.5x LTM EBITDA | Shell's own implied multiple (7.3x), rounded | Judgement | Buyout tab |
| Exit multiple | Equal to entry | No multiple arbitrage assumed | Judgement | Buyout tab |
| Margin path | Base: LTM margin held; downside: fades to 3-year average −0.5pp by year 3; upside: +0.8pp | Consistent with paying for LTM EBITDA | Judgement | Buyout tab (case) |
| Standalone costs | 0.4% of revenue | Costs the parent used to absorb | Judgement | Buyout tab |
| Separation / advisory / exit costs | 1.0% / 1.0% / 1.0% of EV | Convention | Judgement | Inputs (LBO sheet) |
| Leverage | 5.0x pro-forma EBITDA (TLB 3.0x, notes 1.5x, mezzanine 0.5x), capped at 70% of EV | Large-cap sponsor norms | Judgement | Buyout tab |
| Pricing | Base rate 4.05% (US 13-week T-bill) + TLB 3.5%; notes 7.5%; mezzanine 8% cash + 3% PIK | Judgement | Judgement | Buyout tab |
| Tax / interest cap | 28% / net interest deductible up to 30% of EBITDA (no carry-forward) | Simplified UK/EU-style rules | Judgement | Buyout tab |
| Working capital | Group ratio (3.4% of revenue) | Segment data not disclosed | Proxy | n/a |
| Inter-segment revenue | Continues at arm's length | Simplification | Judgement | n/a |

## 5. Merger (Shell acquires BP)

| Assumption | Default | Basis | Type | Change in |
|---|---|---|---|---|
| Closing date | 31 Dec 2026 | Convention | Judgement | `ma.py` |
| Premium | 30% to BP's share price | Typical large-cap premium | Judgement | Deal tab |
| Consideration | 50% new Shell shares at the current price, 50% cash | Judgement | Judgement | Deal tab |
| Acquisition debt | Risk-free + 1.0%, repaid from excess cash before buybacks | Judgement | Judgement | Deal tab |
| Synergies | $3.0bn a year pre-tax, phased 33% / 67% / 100% | Illustrative, not an estimate of real synergies | Judgement | Deal tab |
| Integration costs | 1.2x run-rate synergies, over years 1–2 | Convention | Judgement | Deal tab |
| Purchase accounting | 8% fair-value uplift on BP fixed assets, 15-year life, 25% deferred tax | Illustrative | Judgement | Deal tab |
| Fees | Advisory 0.3% of target EV; financing 1.0% of new debt; expensed at close | Convention | Judgement | Deal tab |
| Divestments | None (0%) by default; sold at 6x EBITDA if set | Competition remedies are uncertain | Judgement | Deal tab |
| Shell buybacks after the deal | Suspended (0%) | Deleveraging priority | Judgement | Deal tab |
| Dividend policy | Shell's standalone dividend per share on the enlarged share count | Convention | Judgement | n/a |
| EPS basis | Constant share counts on both sides; standalone comparator on the same buyback policy | Like-for-like | Method | n/a |

## 6. Portfolio

| Assumption | Default | Basis | Type | Change in |
|---|---|---|---|---|
| Universe | 13 assets chosen by the user | User | User | Portfolio tab |
| Data | Weekly adjusted closes since Jan 2021, in GBP | Yahoo Finance | Data | n/a |
| Covariance | Ledoit-Wolf shrinkage to a scaled identity | Standard estimator | Method | n/a |
| Expected returns | 25% history + 75% CAPM prior (risk-free + beta × 5% ERP) | History alone is too noisy | Judgement | Portfolio tab |
| Risk-free rate | 4.05% (US 13-week T-bill) | A sterling cash rate may differ | Proxy | Portfolio tab |
| Weight cap | 25% per asset, long only | Concentration control | Judgement | Portfolio tab |
| Backtest | 2-year window, rebalance every 4 weeks, 10bp per unit of turnover | Convention | Judgement | Portfolio tab |
| Simulation | Student-t (6 degrees of freedom), monthly, 5,000 paths | Fat tails | Judgement | Portfolio tab |
| Hedging | Local-currency returns, carry ignored | Simplification | Simplification | Portfolio tab toggle |
