"""Market inputs for the DCF: price, share count, beta (vs FTSE 100), USD risk-free proxy, GBP/USD."""
import json
import numpy as np
import pandas as pd
import yfinance as yf

COMPANIES = {"shell": "SHEL.L", "bp": "BP.L"}
out = {}

px = pd.read_csv("data/clean/prices.csv", index_col=0, parse_dates=True)
fx = float(px["GBPUSD"].dropna().iloc[-1])

idx = yf.download(["^FTSE", "^TNX", "^IRX"], start="2021-01-01", auto_adjust=True, progress=False)["Close"]
idx.index = pd.to_datetime(idx.index).tz_localize(None)
tnx = idx["^TNX"].dropna() / 100  # ^TNX quotes the 10y US Treasury yield in percent
rf = float(tnx.iloc[-1])
rf_1y = float(tnx.tail(252).mean())
short_rate = float((idx["^IRX"].dropna() / 100).iloc[-1])  # 13-week T-bill: proxy for the floating base rate
ftse_w = idx["^FTSE"].resample("W-FRI").last().pct_change(fill_method=None)

for name, tkr in COMPANIES.items():
    s = px["Shell" if name == "shell" else "BP"].dropna()
    w = s.resample("W-FRI").last().pct_change(fill_method=None)
    d = pd.concat([w, ftse_w], axis=1, keys=["s", "m"]).dropna()
    beta_raw = float(np.cov(d.s, d.m)[0, 1] / np.var(d.m, ddof=1))
    info = yf.Ticker(tkr).info
    out[name] = dict(
        ticker=tkr,
        price_gbp_pence=float(s.iloc[-1]),
        price_date=str(s.index[-1].date()),
        shares_m=(info.get("sharesOutstanding") or float("nan")) / 1e6,
        beta_raw=round(beta_raw, 3),
        beta_blume=round(0.67 * beta_raw + 0.33, 3),
        beta_obs_weeks=int(len(d)),
    )
out["_common"] = dict(gbpusd=fx, risk_free_spot=rf, risk_free_1y_avg=rf_1y,
                      risk_free_blend=0.5 * rf + 0.5 * rf_1y, short_rate=short_rate, equity_risk_premium=0.05)
json.dump(out, open("data/clean/market_inputs.json", "w"), indent=2)
print(json.dumps(out, indent=2))
