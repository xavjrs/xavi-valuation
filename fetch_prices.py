"""Download adjusted daily closes for the 13 portfolio assets + GBP/USD (+ Shell/BP) via yfinance and QA them."""
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

tickers = {k: v[0] for k, v in {**ASSETS, **EXTRA}.items()}
raw = yf.download(list(tickers.values()), start=START, auto_adjust=True, progress=False, group_by="column")["Close"]
inv = {v: k for k, v in tickers.items()}
px = raw.rename(columns=inv)[list(tickers)]
px.index = pd.to_datetime(px.index).tz_localize(None)

print("rows:", len(px), "| range:", px.index.min().date(), "->", px.index.max().date())
rep = pd.DataFrame({
    "first": px.apply(lambda s: s.first_valid_index().date()),
    "last": px.apply(lambda s: s.last_valid_index().date()),
    "n_obs": px.count(),
    "missing_after_first": px.apply(lambda s: int(s.loc[s.first_valid_index():].isna().sum())),
    "max_1d_move_%": (px.pct_change(fill_method=None).abs().max() * 100).round(1),
    "last_px": px.apply(lambda s: s.dropna().iloc[-1]).round(2),
})
print(rep.to_string())
px.to_csv("data/clean/prices.csv")
