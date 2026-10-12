# XAVI model audit

Run 2026-10-12 19:19: **86 of 86 checks pass.**

## Data

| Status | Check | Detail |
|---|---|---|
| PASS | SHELL FY2021–25: assets = liabilities + equity | max difference $0.0m |
| PASS | SHELL FY2021–25: equity = shareholders + minorities | max difference $0.0m |
| PASS | SHELL FY2021–25: pre-tax profit − tax = net income | max difference $0.0m |
| PASS | SHELL: no missing core lines | 0 missing cells |
| PASS | BP FY2021–25: assets = liabilities + equity | max difference $0.0m |
| PASS | BP FY2021–25: equity = shareholders + minorities | max difference $0.0m |
| PASS | BP FY2021–25: pre-tax profit − tax = net income | max difference $0.0m |
| PASS | BP: no missing core lines | 0 missing cells |
| PASS | Shell segments 2023: revenue_third_party ties to group accounts | segment total 316,620 vs group 316,620 |
| PASS | Shell segments 2023: capex ties to group accounts | segment total 22,993 vs group 22,993 |
| PASS | Shell segments 2023: dda ties to group accounts | segment total 31,290 vs group 31,290 |
| PASS | Shell segments 2023: tax ties to group accounts | segment total 12,991 vs group 12,991 |
| PASS | Shell segments 2023: income ties to group accounts | segment total 19,636 vs group 19,636 |
| PASS | Shell segments 2024: revenue_third_party ties to group accounts | segment total 284,312 vs group 284,312 |
| PASS | Shell segments 2024: capex ties to group accounts | segment total 19,601 vs group 19,601 |
| PASS | Shell segments 2024: dda ties to group accounts | segment total 26,872 vs group 26,872 |
| PASS | Shell segments 2024: tax ties to group accounts | segment total 13,401 vs group 13,401 |
| PASS | Shell segments 2024: income ties to group accounts | segment total 16,521 vs group 16,521 |
| PASS | Shell segments 2025: revenue_third_party ties to group accounts | segment total 266,886 vs group 266,886 |
| PASS | Shell segments 2025: capex ties to group accounts | segment total 18,947 vs group 18,947 |
| PASS | Shell segments 2025: dda ties to group accounts | segment total 25,299 vs group 25,299 |
| PASS | Shell segments 2025: tax ties to group accounts | segment total 11,637 vs group 11,637 |
| PASS | Shell segments 2025: income ties to group accounts | segment total 18,119 vs group 18,119 |
| PASS | Shell segments: every row sums to its reported total | max rounding difference $0m |
| PASS | Price history is recent (≤ 7 days old) | last price 2026-10-12, 0 days old |
| PASS | Market inputs match the latest price date | market inputs 2026-10-12 vs prices 2026-10-12 |
| PASS | Price gaps are holiday-sized only (< 5% of days) | max gaps 52 of 1503 days |

## Forecast

| Status | Check | Detail |
|---|---|---|
| PASS | SHELL bear: balance sheet balances every year | max imbalance 5.8e-11 |
| PASS | SHELL bear: cash rolls forward from the cash flow | max difference 7.3e-12 |
| PASS | SHELL base: balance sheet balances every year | max imbalance 1.2e-10 |
| PASS | SHELL base: cash rolls forward from the cash flow | max difference 1.1e-11 |
| PASS | SHELL bull: balance sheet balances every year | max imbalance 2.9e-11 |
| PASS | SHELL bull: cash rolls forward from the cash flow | max difference 1.1e-11 |
| PASS | BP bear: balance sheet balances every year | max imbalance 8.7e-11 |
| PASS | BP bear: cash rolls forward from the cash flow | max difference 7.3e-12 |
| PASS | BP base: balance sheet balances every year | max imbalance 6.5e-11 |
| PASS | BP base: cash rolls forward from the cash flow | max difference 7.3e-12 |
| PASS | BP bull: balance sheet balances every year | max imbalance 4.4e-11 |
| PASS | BP bull: cash rolls forward from the cash flow | max difference 1.5e-11 |

## DCF

| Status | Check | Detail |
|---|---|---|
| PASS | SHELL: equity bridge adds up |  |
| PASS | SHELL: EV = PV of flows + PV of terminal value |  |
| PASS | SHELL: sensitivity grid centre = point estimate |  |
| PASS | BP: equity bridge adds up |  |
| PASS | BP: EV = PV of flows + PV of terminal value |  |
| PASS | BP: sensitivity grid centre = point estimate |  |

## Monte Carlo

| Status | Check | Detail |
|---|---|---|
| PASS | SHELL: zero-shock path reproduces the DCF | 2,621.1419p vs 2,621.1419p |
| PASS | BP: zero-shock path reproduces the DCF | 907.9631p vs 907.9631p |

## LBO

| Status | Check | Detail |
|---|---|---|
| PASS | Integrated Gas: sources = uses |  |
| PASS | Integrated Gas: returns bridge reconciles |  |
| PASS | Integrated Gas: cash rolls forward | max difference 0.0e+00 |
| PASS | Integrated Gas: financeability reported | financeable |
| PASS | Upstream: sources = uses |  |
| PASS | Upstream: returns bridge reconciles |  |
| PASS | Upstream: cash rolls forward | max difference 0.0e+00 |
| PASS | Upstream: financeability reported | financeable |
| PASS | Marketing: sources = uses |  |
| PASS | Marketing: returns bridge reconciles |  |
| PASS | Marketing: cash rolls forward | max difference 0.0e+00 |
| PASS | Marketing: financeability reported | financeable |
| PASS | Chemicals and Products: sources = uses |  |
| PASS | Chemicals and Products: returns bridge reconciles |  |
| PASS | Chemicals and Products: cash rolls forward | max difference 0.0e+00 |
| PASS | Chemicals and Products: financeability reported | flagged NOT financeable (by design for weak divisions) |
| PASS | Renewables and Energy Solutions: sources = uses |  |
| PASS | Renewables and Energy Solutions: returns bridge reconciles |  |
| PASS | Renewables and Energy Solutions: cash rolls forward | max difference 0.0e+00 |
| PASS | Renewables and Energy Solutions: financeability reported | flagged NOT financeable (by design for weak divisions) |

## Merger

| Status | Check | Detail |
|---|---|---|
| PASS | default terms: opening balance sheet balances | -2.9e-11 |
| PASS | default terms: pro forma forecast balances |  |
| PASS | default terms: sources = uses |  |
| PASS | default terms: goodwill = price − fair value of net assets |  |
| PASS | all stock, 10% divested: opening balance sheet balances | -5.8e-11 |
| PASS | all stock, 10% divested: pro forma forecast balances |  |
| PASS | all stock, 10% divested: sources = uses |  |
| PASS | all stock, 10% divested: goodwill = price − fair value of net assets |  |
| PASS | all cash, 50% premium: opening balance sheet balances | -2.9e-11 |
| PASS | all cash, 50% premium: pro forma forecast balances |  |
| PASS | all cash, 50% premium: sources = uses |  |
| PASS | all cash, 50% premium: goodwill = price − fair value of net assets |  |

## Portfolio

| Status | Check | Detail |
|---|---|---|
| PASS | All strategies: weights sum to 100% within caps |  |
| PASS | Minimum-variance portfolio has the lowest volatility |  |
| PASS | Maximum-Sharpe portfolio has the highest Sharpe ratio |  |
| PASS | Backtest uses no future data |  |

## Excel

| Status | Check | Detail |
|---|---|---|
| PASS | Workbook has no formula errors | 1,082 formulas, 0 errors, 0 uncalculated |
| PASS | Workbook reconciles to the Python engine | 36 of 36 reconciliation lines pass |

## Tests

| Status | Check | Detail |
|---|---|---|
| PASS | Automated test suite passes | 87 passed in 6.81s |
