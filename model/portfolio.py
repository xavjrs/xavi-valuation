"""Portfolio and quant engine for a sterling investor.

Data
- Adjusted daily closes (dividends reinvested) from data/clean/prices.csv. UK lines are quoted in pence, US lines in
  dollars. Every series is converted to GBP; USD assets can optionally be shown fully hedged (local-currency returns,
  hedge carry ignored).
- Weekly (Friday) returns drive estimation and optimisation: UK and US markets close at different times, and daily
  returns understate cross-market correlation. Daily returns are used only for VaR and drawdowns.

Estimation
- Covariance: sample covariance shrunk towards a scaled identity (Ledoit-Wolf, 2004).
- Expected returns: a blend of the historical mean and a CAPM prior (risk-free + beta to the FTSE 100 x ERP). History
  alone is a very noisy estimate of the future (Palantir's last five years would dominate everything).

Portfolios: minimum variance, maximum Sharpe, risk parity, maximum diversification, equal weight, custom. Long only,
fully invested, optional cap per asset. Walk-forward backtest with no look-ahead, and a Student-t Monte Carlo.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from scipy.optimize import minimize

BASKET = {  # name -> (sector, quote currency)
    "Barclays": ("Banks", "GBp"), "Prudential": ("Insurance", "GBp"), "Rolls-Royce": ("Aerospace", "GBp"),
    "Glencore": ("Mining", "GBp"), "SSE": ("Utilities", "GBp"), "United Utilities": ("Utilities", "GBp"),
    "BT": ("Telecom", "GBp"), "British American Tobacco": ("Tobacco", "GBp"), "AstraZeneca": ("Healthcare", "GBp"),
    "Palantir": ("Technology", "USD"), "Coca-Cola": ("Consumer", "USD"), "Equinix": ("Real estate", "USD"),
    "EEMA": ("EM Asia equity", "USD"),
}
BENCH = "FTSE 100 ETF"
WEEKS = 52
DAYS = 252


# ───────────────────────── data ─────────────────────────
def load_prices() -> pd.DataFrame:
    return pd.read_csv("data/clean/prices.csv", index_col=0, parse_dates=True)


def gbp_prices(px: pd.DataFrame, assets: list[str], hedged: bool = False) -> pd.DataFrame:
    """Daily prices in GBP (or local currency for hedged USD lines), calendar-aligned with a short forward fill."""
    cols = list(assets) + [BENCH]
    p = px[cols + ["GBPUSD"]].ffill(limit=5)
    out = pd.DataFrame(index=p.index)
    for c in cols:
        ccy = BASKET.get(c, ("", "GBp"))[1]
        if ccy == "GBp":
            out[c] = p[c] / 100
        else:
            out[c] = p[c] if hedged else p[c] / p["GBPUSD"]
    return out.dropna()


def returns(px_gbp: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    if freq == "W":
        return px_gbp.resample("W-FRI").last().pct_change(fill_method=None).dropna()
    return px_gbp.pct_change(fill_method=None).dropna()


def fx_decomposition(px: pd.DataFrame) -> pd.DataFrame:
    """For each USD asset: volatility in USD, in GBP, and the share of GBP variance explained by the FX leg."""
    usd = [a for a, (_, c) in BASKET.items() if c == "USD"]
    p = px[usd + ["GBPUSD"]].ffill(limit=5).dropna().resample("W-FRI").last()
    r_loc = p[usd].pct_change(fill_method=None)
    fx = (1 / p["GBPUSD"]).pct_change(fill_method=None)       # GBP return of holding one dollar
    rows = []
    for a in usd:
        r_gbp = (1 + r_loc[a]) * (1 + fx) - 1
        d = pd.concat([r_loc[a], fx, r_gbp], axis=1, keys=["loc", "fx", "gbp"]).dropna()
        v_loc, v_fx, v_gbp = d.var() * WEEKS
        rows.append(dict(asset=a, vol_usd=np.sqrt(v_loc), vol_gbp=np.sqrt(v_gbp), vol_fx=np.sqrt(v_fx),
                         corr_asset_fx=d["loc"].corr(d["fx"]), fx_share_of_variance=(v_gbp - v_loc) / v_gbp))
    return pd.DataFrame(rows).set_index("asset")


# ───────────────────────── estimation ─────────────────────────
def ledoit_wolf(r: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Ledoit-Wolf (2004) shrinkage of the sample covariance towards a scaled identity. Returns (cov, shrinkage)."""
    x = r.values - r.values.mean(axis=0)
    n, p = x.shape
    s = x.T @ x / n
    mu = np.trace(s) / p
    d2 = np.sum((s - mu * np.eye(p)) ** 2) / p
    sq = np.einsum('ki,ki->k', x, x)
    b_bar2 = ((sq ** 2).sum() - 2 * np.einsum('ki,ij,kj->', x, s, x) + n * np.sum(s ** 2)) / n ** 2 / p
    b2 = min(b_bar2, d2)
    delta = b2 / d2 if d2 > 0 else 1.0
    sig = (1 - delta) * s + delta * mu * np.eye(p)
    sig *= n / (n - 1)                                     # unbiased scaling to match sample variance convention
    return pd.DataFrame(sig, index=r.columns, columns=r.columns), float(delta)


@dataclass
class Estimates:
    mu: pd.Series            # annual expected return (blended)
    mu_hist: pd.Series
    mu_prior: pd.Series
    cov: pd.DataFrame        # annual covariance (shrunk)
    beta: pd.Series          # to the FTSE 100 ETF
    shrinkage: float
    rf: float
    n_obs: int


def estimate(r_w: pd.DataFrame, assets: list[str], rf: float = 0.04, erp: float = 0.05, hist_weight: float = 0.25) -> Estimates:
    ra = r_w[assets]
    cov_w, delta = ledoit_wolf(ra)
    rb = r_w[BENCH]
    beta = ra.apply(lambda c: c.cov(rb) / rb.var())
    mu_hist = ra.mean() * WEEKS
    mu_prior = rf + beta * erp
    mu = hist_weight * mu_hist + (1 - hist_weight) * mu_prior
    return Estimates(mu=mu, mu_hist=mu_hist, mu_prior=mu_prior, cov=cov_w * WEEKS, beta=beta, shrinkage=delta, rf=rf, n_obs=len(ra))


# ───────────────────────── portfolio maths ─────────────────────────
def port_stats(w: np.ndarray, e: Estimates) -> dict:
    w = np.asarray(w, float)
    mu, cov = e.mu.values, e.cov.values
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ cov @ w))
    sd = np.sqrt(np.diag(cov))
    return dict(ret=ret, vol=vol, sharpe=(ret - e.rf) / vol if vol > 0 else np.nan, div_ratio=float(w @ sd) / vol,
                beta=float(w @ e.beta.values))


def risk_contributions(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Component contributions to volatility; they sum to portfolio volatility."""
    w = np.asarray(w, float)
    vol = np.sqrt(w @ cov @ w)
    return w * (cov @ w) / vol


def effective_bets(w: np.ndarray, cov: np.ndarray) -> float:
    """Exponential of the entropy of risk shares: 1 = one bet, n = n equal bets."""
    rc = risk_contributions(w, cov)
    s = np.clip(rc / rc.sum(), 1e-12, None)
    return float(np.exp(-(s * np.log(s)).sum()))


def _solve(obj, n: int, cap: float, extra_cons: list | None = None, x0: np.ndarray | None = None, jac=None) -> np.ndarray:
    """Long-only, fully invested SLSQP with an optional analytic gradient (much faster than finite differences)."""
    cap = max(cap, 1.0 / n + 1e-9)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones_like(w)}] + (extra_cons or [])
    x0 = np.full(n, 1.0 / n) if x0 is None else x0
    res = minimize(obj, x0, method="SLSQP", jac=jac, bounds=[(0.0, cap)] * n, constraints=cons,
                   options=dict(maxiter=500, ftol=1e-12))
    w = np.clip(res.x, 0, None)
    return w / w.sum()


def min_variance(e: Estimates, cap: float = 1.0) -> np.ndarray:
    c = e.cov.values
    return _solve(lambda w: w @ c @ w, len(e.mu), cap, jac=lambda w: 2 * c @ w)


def _neg_ratio(num_vec: np.ndarray, c: np.ndarray, rf: float = 0.0):
    """-(w'v - rf) / sqrt(w'Cw) and its gradient: used for maximum Sharpe (v = mu) and maximum diversification (v = sd)."""
    def f(w):
        return -(w @ num_vec - rf) / np.sqrt(w @ c @ w)

    def g(w):
        vol = np.sqrt(w @ c @ w)
        return -(num_vec * vol - (w @ num_vec - rf) * (c @ w) / vol) / vol ** 2
    return f, g


def max_sharpe(e: Estimates, cap: float = 1.0) -> np.ndarray:
    mu, c = e.mu.values, e.cov.values
    f, g = _neg_ratio(mu, c, e.rf)
    best, best_s = None, -np.inf
    for x0 in (np.full(len(mu), 1 / len(mu)), min_variance(e, cap)):   # two starts guard against a poor local optimum
        w = _solve(f, len(mu), cap, x0=x0, jac=g)
        s_ = -f(w)
        if s_ > best_s:
            best, best_s = w, s_
    return best


def risk_parity(e: Estimates, cap: float = 1.0) -> np.ndarray:
    """Equal risk contribution via the convex formulation of Spinu (2013): minimise 0.5 y'Cy - (1/n) sum log y over y > 0,
    then normalise. Falls back to a direct (slower) solve only if the result breaks the weight cap."""
    c = e.cov.values
    n = len(e.mu)
    b = np.full(n, 1.0 / n)
    y0 = 1 / np.sqrt(np.diag(c))
    res = minimize(lambda y: 0.5 * y @ c @ y - b @ np.log(y), y0, jac=lambda y: c @ y - b / y,
                   method="L-BFGS-B", bounds=[(1e-12, None)] * n, options=dict(maxiter=2000, gtol=1e-14, ftol=1e-16))
    w = res.x / res.x.sum()
    if w.max() <= max(cap, 1.0 / n) + 1e-9:
        return w

    def obj(w_):
        rc = risk_contributions(w_, c)
        return float(((rc / rc.sum() - 1.0 / n) ** 2).sum()) * 1e4
    return _solve(obj, n, cap, x0=np.minimum(w, cap) / np.minimum(w, cap).sum())


def max_diversification(e: Estimates, cap: float = 1.0) -> np.ndarray:
    c = e.cov.values
    f, g = _neg_ratio(np.sqrt(np.diag(c)), c)
    return _solve(f, len(c), cap, jac=g)


def equal_weight(e: Estimates, cap: float = 1.0) -> np.ndarray:
    return np.full(len(e.mu), 1.0 / len(e.mu))


STRATEGIES = {"Max Sharpe": max_sharpe, "Min variance": min_variance, "Risk parity": risk_parity,
              "Max diversification": max_diversification, "Equal weight": equal_weight}


def frontier(e: Estimates, cap: float = 1.0, n_points: int = 30) -> pd.DataFrame:
    mu, c = e.mu.values, e.cov.values
    w_mv = min_variance(e, cap)
    r_lo = float(w_mv @ mu)
    w_hi = _solve(lambda w: -(w @ mu), len(mu), cap, jac=lambda w: -mu)
    r_hi = float(w_hi @ mu)
    pts = []
    for tgt in np.linspace(r_lo, r_hi, n_points):
        w = _solve(lambda w: w @ c @ w, len(mu), cap, [{"type": "eq", "fun": lambda w, t=tgt: w @ mu - t, "jac": lambda w: mu}],
                   x0=w_mv, jac=lambda w: 2 * c @ w)
        w_mv = w                                                      # warm-start the next point from this one
        pts.append(dict(ret=float(w @ mu), vol=float(np.sqrt(w @ c @ w))))
    return pd.DataFrame(pts)


# ───────────────────────── risk on realised returns ─────────────────────────
def realised(w: pd.Series, r: pd.DataFrame, periods: int) -> dict:
    """Stats of a constant-weight (rebalanced each period) portfolio on a return panel."""
    pr = r[w.index] @ w.values
    wealth = (1 + pr).cumprod()
    dd = wealth / wealth.cummax() - 1
    return dict(series=pr, wealth=wealth, drawdown=dd, ann_ret=float(wealth.iloc[-1] ** (periods / len(pr)) - 1),
                ann_vol=float(pr.std() * np.sqrt(periods)), max_dd=float(dd.min()))


def var_table(pr_daily: pd.Series, levels=(0.95, 0.99), horizon_days: int = 10) -> pd.DataFrame:
    """Historical and parametric VaR / CVaR, 1-day and `horizon_days` (square-root-of-time), as positive loss %."""
    rows = []
    from statistics import NormalDist
    mu, sd = pr_daily.mean(), pr_daily.std()
    for lv in levels:
        q = np.quantile(pr_daily, 1 - lv)
        hist_var, hist_cvar = -q, -pr_daily[pr_daily <= q].mean()
        z = NormalDist().inv_cdf(lv)
        par_var = z * sd - mu
        par_cvar = sd * np.exp(-z * z / 2) / np.sqrt(2 * np.pi) / (1 - lv) - mu
        k = np.sqrt(horizon_days)
        rows.append({"Confidence": f"{lv:.0%}", "Historical VaR 1d": hist_var, "Historical CVaR 1d": hist_cvar,
                     "Normal VaR 1d": par_var, "Normal CVaR 1d": par_cvar,
                     f"Historical VaR {horizon_days}d": hist_var * k, f"Normal VaR {horizon_days}d": par_var * k})
    return pd.DataFrame(rows).set_index("Confidence")


def stress_tests(w: pd.Series, e: Estimates, r_w: pd.DataFrame, hedged: bool) -> pd.DataFrame:
    usd_w = sum(w[a] for a in w.index if BASKET[a][1] == "USD")
    pr = r_w[w.index] @ w.values
    monthly = (1 + pr).resample("ME").prod() - 1
    rows = [
        ("UK equity sell-off: FTSE 100 -20% (via betas)", float((w * e.beta[w.index]).sum() * -0.20)),
        ("Sterling +10% against the dollar", 0.0 if hedged else float(usd_w * (1 / 1.10 - 1))),
        ("Sterling -10% against the dollar", 0.0 if hedged else float(usd_w * (1 / 0.90 - 1))),
        (f"Worst week in sample ({pr.idxmin().date()})", float(pr.min())),
        (f"Worst month in sample ({monthly.idxmin():%b %Y})", float(monthly.min())),
    ]
    return pd.DataFrame(rows, columns=["Scenario", "Portfolio return"]).set_index("Scenario")


# ───────────────────────── walk-forward backtest ─────────────────────────
def backtest(r_w: pd.DataFrame, assets: list[str], window: int = 104, step: int = 4, cap: float = 1.0, rf: float = 0.04,
             erp: float = 0.05, hist_weight: float = 0.25, cost_bps: float = 10.0, strategies: list[str] | None = None) -> dict:
    """Re-estimate on the trailing `window` weeks and rebalance every `step` weeks. Weights at a rebalance date use
    only returns strictly before it (no look-ahead). Transaction costs = turnover x cost_bps."""
    strategies = strategies or list(STRATEGIES)
    dates = r_w.index
    out = {s: [] for s in strategies}
    weights = {s: [] for s in strategies}
    prev = {s: None for s in strategies}
    turnover = {s: [] for s in strategies}
    for start in range(window, len(dates), step):
        est = estimate(r_w.iloc[start - window:start], assets, rf, erp, hist_weight)
        hold = r_w.iloc[start:start + step]
        for s in strategies:
            w = STRATEGIES[s](est, cap)
            to = 1.0 if prev[s] is None else float(np.abs(w - prev[s]).sum())
            prev[s] = w
            turnover[s].append(to)
            weights[s].append(pd.Series(w, index=assets, name=dates[start]))
            pr = hold[assets] @ w
            pr.iloc[0] -= to * cost_bps / 1e4
            out[s].append(pr)
    rets = pd.DataFrame({s: pd.concat(v) for s, v in out.items()})
    rets[BENCH] = r_w[BENCH].loc[rets.index]
    wealth = (1 + rets).cumprod()
    stats = {}
    for c in rets.columns:
        pr = rets[c]
        ann = float(wealth[c].iloc[-1] ** (WEEKS / len(pr)) - 1)
        vol = float(pr.std() * np.sqrt(WEEKS))
        dd = float((wealth[c] / wealth[c].cummax() - 1).min())
        stats[c] = dict(ann_return=ann, ann_vol=vol, sharpe=(ann - rf) / vol, max_drawdown=dd,
                        avg_turnover=float(np.mean(turnover[c][1:])) if c in turnover and len(turnover[c]) > 1 else 0.0)
    return dict(returns=rets, wealth=wealth, stats=pd.DataFrame(stats).T,
                weights={s: pd.DataFrame(v) for s, v in weights.items()}, start=rets.index[0])


# ───────────────────────── forward simulation ─────────────────────────
def simulate(w: np.ndarray, e: Estimates, years: int = 5, n: int = 5000, df: int = 6, seed: int = 11) -> dict:
    """Monthly multivariate Student-t returns with the estimated mean and covariance; wealth paths from 1.0."""
    rng = np.random.default_rng(seed)
    m = years * 12
    cov_m = e.cov.values / 12
    mu_m = e.mu.values / 12
    L = np.linalg.cholesky(cov_m + 1e-12 * np.eye(len(mu_m)))
    z = rng.standard_normal((n, m, len(mu_m)))
    chi = rng.chisquare(df, (n, m, 1))
    t = z / np.sqrt(chi / df) * np.sqrt((df - 2) / df)      # unit-variance Student-t
    r = mu_m + t @ L.T
    pr = r @ np.asarray(w)
    wealth = np.cumprod(1 + pr, axis=1)
    term = wealth[:, -1]
    return dict(wealth=wealth, terminal=term, pct=np.percentile(wealth, [5, 25, 50, 75, 95], axis=0),
                prob_loss=float((term < 1).mean()), prob_below_cash=float((term < (1 + e.rf) ** years).mean()),
                p5=float(np.percentile(term, 5)), p50=float(np.median(term)), p95=float(np.percentile(term, 95)))
