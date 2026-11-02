"""Download adjusted daily closes for the 13 portfolio assets + Shell, BP, the FTSE 100 ETF and GBP/USD (yfinance).

Safe to run unattended (the daily GitHub Action uses it): the download is retried, the result is validated, and
data/clean/prices.csv is only replaced if every series is complete and recent. On failure the old file is kept and
the script exits with an error, so nothing half-downloaded is ever published.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

# name -> (ticker, quote currency)
ASSETS = {
    "Barclays": ("BARC.L", "GBp"), "Prudential": ("PRU.L", "GBp"), "Rolls-Royce": ("RR.L", "GBp"),
    "Glencore": ("GLEN.L", "GBp"), "SSE": ("SSE.L", "GBp"), "United Utilities": ("UU.L", "GBp"),
    "BT": ("BT-A.L", "GBp"), "British American Tobacco": ("BATS.L", "GBp"), "AstraZeneca": ("AZN.L", "GBp"),
    "Palantir": ("PLTR", "USD"), "Coca-Cola": ("KO", "USD"), "Equinix": ("EQIX", "USD"), "EEMA": ("EEMA", "USD"),
}
EXTRA = {"Shell": ("SHEL.L", "GBp"), "BP": ("BP.L", "GBp"), "FTSE 100 ETF": ("ISF.L", "GBp"), "GBPUSD": ("GBPUSD=X", "FX")}
START = "2021-01-01"
OUT = Path("data/clean/prices.csv")
MAX_STALE_DAYS = 7          # every series must have a price within this many days of the newest date
MAX_LAST_MOVE = 0.6         # a >60% one-day move on the latest day is treated as bad data


def download(tickers: dict, attempts: int = 5) -> pd.DataFrame:
    inv = {v: k for k, v in tickers.items()}
    for i in range(attempts):
        try:
            raw = yf.download(list(tickers.values()), start=START, auto_adjust=True, progress=False, group_by="column", threads=False)["Close"]
            px = raw.rename(columns=inv)
            missing = [c for c in tickers if c not in px.columns or px[c].dropna().empty]
            if not missing:
                px = px[list(tickers)]
                px.index = pd.to_datetime(px.index).tz_localize(None)
                return px
            print(f"attempt {i + 1}: no data for {missing}")
        except Exception as exc:                       # rate limits and transient network errors
            print(f"attempt {i + 1}: {type(exc).__name__}: {exc}")
        time.sleep(20 * (i + 1))
    sys.exit("price download failed after retries; keeping the existing prices.csv")


def validate(px: pd.DataFrame) -> list[str]:
    problems = []
    newest = px.index.max()
    for c in px.columns:
        s = px[c].dropna()
        if (newest - s.index[-1]).days > MAX_STALE_DAYS:
            problems.append(f"{c}: last price {s.index[-1].date()} is stale (newest date {newest.date()})")
        if len(s) > 1 and abs(s.iloc[-1] / s.iloc[-2] - 1) > MAX_LAST_MOVE:
            problems.append(f"{c}: implausible last move {s.iloc[-1] / s.iloc[-2] - 1:+.0%}")
    if OUT.exists():
        old = pd.read_csv(OUT, index_col=0, parse_dates=True)
        if newest < old.index.max():
            problems.append(f"new data ends {newest.date()}, before the existing file ({old.index.max().date()})")
        if len(px) < 0.98 * len(old):
            problems.append(f"new data has {len(px)} rows vs {len(old)} before")
    return problems


def main():
    tickers = {k: v[0] for k, v in {**ASSETS, **EXTRA}.items()}
    px = download(tickers)
    problems = validate(px)
    rep = pd.DataFrame({
        "last": px.apply(lambda s: s.last_valid_index().date()),
        "n_obs": px.count(),
        "max_1d_move_%": (px.pct_change(fill_method=None).abs().max() * 100).round(1),
        "last_px": px.apply(lambda s: s.dropna().iloc[-1]).round(2),
    })
    print("rows:", len(px), "| range:", px.index.min().date(), "->", px.index.max().date())
    print(rep.to_string())
    if problems:
        print("\n".join("PROBLEM " + p for p in problems))
        sys.exit("validation failed; keeping the existing prices.csv")
    tmp = OUT.with_suffix(".tmp")
    px.to_csv(tmp)
    tmp.replace(OUT)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
