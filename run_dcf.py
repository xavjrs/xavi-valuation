import sys
import pandas as pd
from model.three_statement import load_history, default_assumptions, forecast, SCENARIOS
from model.dcf import dcf, sensitivity, wacc
from model.setup import load_market, valuation_inputs, bridge_for

company = sys.argv[1] if len(sys.argv) > 1 else "shell"
h = load_history(company)
mk = load_market()
m = mk[company]
v = valuation_inputs(h, mk, company)

print(f"{company.upper()}  price {m['price_gbp_pence']:,.0f}p ({m['price_date']})  beta {m['beta_blume']}  "
      f"rf {v.risk_free:.2%}  WACC {wacc(v):.2%}")
rows = {}
for sc in SCENARIOS:
    a = default_assumptions(h, sc)
    out = forecast(h, a)
    r = dcf(out, v, bridge_for(h, mk, company, a))
    rows[sc] = dict(ev_bn=r["ev"] / 1e3, equity_bn=r["equity_value"] / 1e3, tv_share=r["tv_share_of_ev"],
                    gordon_implied_multiple=r["implied_exit_ev_ebitda"], gordon_pence=r["value_per_share_gbp_pence"],
                    multiple_pence=r["multiple_method"]["value_per_share_gbp_pence"],
                    gordon_vs_mkt=r["value_per_share_gbp_pence"] / m["price_gbp_pence"] - 1)
    if sc == "base":
        base = (out, a, r)
print(pd.DataFrame(rows).T.to_string(float_format=lambda x: f"{x:,.2f}"))
out, a, r = base
print("\nBase bridge (USD bn):", {k: round(x / 1e3, 1) for k, x in r["bridge"].items()})
print("margin y1", round(a.ebit_margin[0], 4), "tax y1/y10", round(a.tax_rate[0], 3), round(a.tax_rate[-1], 3),
      "jv%", round(a.jv_pct[0], 4))
print(out["kpis"].round(2).to_string())
w0 = wacc(v)
b = bridge_for(h, mk, company, a)
sens = sensitivity(out, v, b, [w0 + d for d in (-0.01, -0.005, 0, 0.005, 0.01)], [0.005, 0.01, 0.015, 0.02, 0.025])
print(sens.to_string(float_format=lambda x: f"{x:,.0f}"))
