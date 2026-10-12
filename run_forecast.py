import sys
import pandas as pd
from model.three_statement import load_history, default_assumptions, forecast, SCENARIOS

pd.options.display.float_format = "{:,.1f}".format
company = sys.argv[1] if len(sys.argv) > 1 else "shell"
h = load_history(company)
for sc in SCENARIOS:
    out = forecast(h, default_assumptions(h, sc))
    for name, df in out.items():
        df.to_csv(f"output/{company}_{sc}_{name}.csv")
    if sc == "base":
        for name, df in out.items():
            print(f"\n--- {company.upper()} {sc}: {name} (USD m) ---")
            print(df.to_string())
    bc = out["balance_sheet"].loc["balance_check"].abs().max()
    mincash = out["balance_sheet"].loc["cash"].min()
    lev = out["kpis"].loc["net_debt_to_ebitda"].iloc[-1]
    print(f"[{sc}] max |balance check| = {bc:.2e}   min cash = {mincash:,.0f}   2030 net debt/EBITDA = {lev:.2f}x")
