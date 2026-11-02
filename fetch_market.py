"""Market inputs for the DCF: price, share count, beta (vs FTSE 100), US 10-year and 13-week yields, GBP/USD.

Run after fetch_prices.py. Safe to run unattended: downloads are retried, any field that cannot be refreshed keeps its
previous value (and says so), and every value is range-checked before data/clean/market_inputs.json is replaced.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

COMPANIES = {"shell": ("SHEL.L", "Shell"), "bp": ("BP.L", "BP")}
OUT = Path("data/clean/market_inputs.json")
RANGES = {"gbpusd": (0.8, 2.0), "risk_free_spot": (0.0, 0.15), "risk_free_1y_avg": (0.0, 0.15), "short_rate": (0.0, 0.15),
          "beta_blume": (0.2, 2.5), "shares_m": (1_000, 50_000), "price_gbp_pence": (50, 20_000)}


def retry(fn, what: str, attempts: int = 5):
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            print(f"{what}, attempt {i + 1}: {type(exc).__name__}: {exc}")
            time.sleep(15 * (i + 1))
    return None


def main():
    prev = json.load(open(OUT)) if OUT.exists() else {}
    px = pd.read_csv("data/clean/prices.csv", index_col=0, parse_dates=True)
    fx = float(px["GBPUSD"].dropna().iloc[-1])

    def get_index():
        d = yf.download(["^FTSE", "^TNX", "^IRX"], start="2021-01-01", auto_adjust=True, progress=False, threads=False)["Close"]
        if d.empty or d["^TNX"].dropna().empty:
            raise ValueError("empty index download")
        return d
    idx = retry(get_index, "index download")
    if idx is None:
        sys.exit("index download failed; keeping the existing market_inputs.json")
    idx.index = pd.to_datetime(idx.index).tz_localize(None)
    tnx = idx["^TNX"].dropna() / 100                      # ^TNX quotes the 10y US Treasury yield in percent
    rf, rf_1y = float(tnx.iloc[-1]), float(tnx.tail(252).mean())
    short_rate = float((idx["^IRX"].dropna() / 100).iloc[-1])  # 13-week T-bill: proxy for the floating base rate
    ftse_w = idx["^FTSE"].resample("W-FRI").last().pct_change(fill_method=None)

    out, notes = {}, []
    for name, (tkr, col) in COMPANIES.items():
        s = px[col].dropna()
        w = s.resample("W-FRI").last().pct_change(fill_method=None)
        d = pd.concat([w, ftse_w], axis=1, keys=["s", "m"]).dropna()
        beta_raw = float(np.cov(d.s, d.m)[0, 1] / np.var(d.m, ddof=1))
        info = retry(lambda: yf.Ticker(tkr).info, f"{tkr} info") or {}
        shares = info.get("sharesOutstanding")
        if not shares:                                    # Yahoo often withholds this from cloud servers
            shares = prev.get(name, {}).get("shares_m", float("nan")) * 1e6
            notes.append(f"{name}: share count not available, kept previous value")
        out[name] = dict(ticker=tkr, price_gbp_pence=float(s.iloc[-1]), price_date=str(s.index[-1].date()),
                         shares_m=shares / 1e6, beta_raw=round(beta_raw, 3), beta_blume=round(0.67 * beta_raw + 0.33, 3),
                         beta_obs_weeks=int(len(d)))
    out["_common"] = dict(gbpusd=fx, risk_free_spot=rf, risk_free_1y_avg=rf_1y, risk_free_blend=0.5 * rf + 0.5 * rf_1y,
                          short_rate=short_rate, equity_risk_premium=0.05)

    problems = []
    for block in [out["_common"], out["shell"], out["bp"]]:
        for k, (lo, hi) in RANGES.items():
            if k in block and not (lo <= block[k] <= hi):
                problems.append(f"{k}={block[k]} outside [{lo}, {hi}]")
    print(json.dumps(out, indent=2))
    for n in notes:
        print("NOTE", n)
    if problems:
        print("\n".join("PROBLEM " + p for p in problems))
        sys.exit("validation failed; keeping the existing market_inputs.json")
    tmp = OUT.with_suffix(".tmp")
    json.dump(out, open(tmp, "w"), indent=2)
    tmp.replace(OUT)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
