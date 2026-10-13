"""What history says: the launch model (docs/phase2-plan.md section 3).

    python -m analysis.model --data-dir _data --gp-dir _gp --out site/public/data

Fits negative binomial models (log link) of 30-day reviews on niche
competition, Steam events, price and the other predictors in
`analysis.features`, separately for paid and free games, with standard errors
clustered by launch week. Writes model.json (effects as rate ratios with 95%
intervals, sample sizes, checks, caveats) and prints a summary.

Checks: a hurdle model; the revenue proxy (reviews x price, paid games);
small games only; a placebo (the same competition measure, 8 weeks after
launch); top 5 and top 20 tags; the same primary tag; same price tier; with and
without the pre-launch follower control; 2026 launches held out against a
baseline of genre, year and price; and a chance test for the event indicators
(fake event windows on random weeks).

Needs the `analysis` extra (pandas, statsmodels). Reads only local files.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
import warnings
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import events as event_data
from pipeline import storage

from . import features as F

GENRES = 30
HELD_OUT_FROM = date(2026, 1, 1)
PLACEBO_WEEKS = 8
SMALL_PRICE = 20        # small games: under $20, no franchise, publisher with at most 2 earlier launches,
SMALL_REACH = 2         # launched from F.REACH_FULL_FROM (earlier, publisher reach is undercounted)
MIN_FIT = 100           # fewer games: a model is not fitted
MIN_WEEKS = 20          # fewer launch weeks: no clustering, and the result is marked preliminary
FOLLOWER_FROM = date(2024, 6, 1)  # follower history starts 2024-03-15
HEADLINE_COVERAGE = 0.9  # the follower-controlled fit leads once this share of eligible launches have followers
HEADLINE_WEEKS = 52
MAX_ZERO_SHARE = 0.8     # a group where more launches than this have no reviews is marked unreliable
FREE_RECOUNTED = 0.95    # the free model is read once this share of free launches are recounted (free_recount)
HOUR_BANDS = ((0, "0_5"), (6, "6_9"), (10, "10_12"), (13, "13_17"), (18, "18_23"))
HOUR_BASE = "10_12"
COMPETITION = ("competition", "comp_tier", "comp_top5", "comp_top20", "comp_primary", "comp_placebo",
               "comp_tier_placebo")
PLACEBO = {"competition": "comp_placebo", "comp_tier": "comp_tier_placebo"}  # the same rule, 8 weeks later
PERMUTED = ("sale", "next_fest", "themed_fest", "cn_spring", "cn_national", "us_thanksgiving", "xmas_newyear")
PERMUTATIONS = 1000     # fake window sets per event indicator in the chance test
CN_HOLIDAYS = ("cn_spring", "cn_national")
LOG2 = math.log(2)

LABELS = {
    "competition": "one more launch in the same niche that week",
    "comp_tier": "one more launch in the same niche and price tier that week",
    "comp_top5": "one more same-niche launch that week (niche from the top 5 tags)",
    "comp_top20": "one more same-niche launch that week (niche from the top 20 tags)",
    "comp_primary": "one more launch with the same primary tag that week",
    "comp_placebo": "one more same-niche launch 8 weeks after launch (placebo)",
    "comp_tier_placebo": "one more same-niche, same-tier launch 8 weeks after launch (placebo)",
    "big_competitor": "a big paid release on Steam within 3 days",
    "attention_release": "a big free-to-play or console-only release within 3 days",
    "sale": "launch during a seasonal sale",
    "pre_sale": "launch in the 7 days before a seasonal sale",
    "next_fest": "launch during Next Fest",
    "demo_last_fest": "demo out during the last Next Fest before launch",
    "demo_with_fest": "a demo out by the end of the last Next Fest, against no demo (demo times demo_last_fest)",
    "themed_fest": "launch during a themed fest for one of its top tags",
    "cn_spring": "launch during China's Spring Festival holiday (games without Simplified Chinese)",
    "cn_national": "launch during China's National Day holiday (games without Simplified Chinese)",
    "cn_spring_schinese": "launch during China's Spring Festival holiday (games with Simplified Chinese: "
                          "main effect times extra)",
    "cn_national_schinese": "launch during China's National Day holiday (games with Simplified Chinese: "
                            "main effect times extra)",
    "cn_spring_x_schinese": "Spring Festival launch with Simplified Chinese (extra, on top)",
    "cn_national_x_schinese": "National Day launch with Simplified Chinese (extra, on top)",
    "us_thanksgiving": "launch between US Thanksgiving and Cyber Monday",
    "xmas_newyear": "launch between Christmas and New Year",
    "early_access": "Early Access launch",
    "demo": "had a demo before launch",
    "franchise": "part of a franchise",
    "log_reach": "publisher's earlier launches, per doubling (of 1 + count)",
    "log_price": "own price, per doubling, with the niche's price held fixed",
    "under_5": "price under $5",
    "log_niche_price": "the niche's median price (launches in the year before), per doubling, own price held fixed",
    "n_languages": "one more supported language",
    "en_audio": "English audio",
    "log_followers": "pre-launch followers, per doubling (of 1 + count)",
    **{f"lang_{x}": f"supports {x}" for x in F.LANG_FLAGS},
    **{f"hour_{b}": f"launch hour {b.replace('_', ' to ')} Pacific (against 10 to 12)" for _, b in HOUR_BANDS
       if b != HOUR_BASE},
}
DOUBLING = {"log_reach", "log_price", "log_niche_price", "log_followers"}
KEY_EFFECTS = ("competition", "big_competitor", "sale", "pre_sale", "next_fest", "demo_last_fest", "themed_fest",
               "cn_spring", "cn_national", "us_thanksgiving", "xmas_newyear", "early_access", "demo",
               "log_price", "under_5", "log_niche_price")

log = logging.getLogger("model")


# --- data -------------------------------------------------------------------

def build_frames(data_dir: Path, events_path: Path, gp_dir: Path | None = None,
                 today: date | None = None) -> tuple[dict[str, pd.DataFrame], dict]:
    """The paid and free model frames, with every predictor, and counts for the report."""
    df = F.load_history(data_dir / "history" / "games.csv")
    info = {"prelaunch_tags": F.prelaunch_tags(df, data_dir / "upcoming" / "apps.csv")}
    if today is not None:  # as the data stood on `today`: later launches are neither competition nor placebo
        df = df[df["launch_date"] <= today].copy()
    data_end = max(df["launch_date"])
    today = today or data_end
    df["reach"] = F.publisher_reach(df)
    sample, counts = F.sample(df, today)
    info["sample"] = counts
    info["free_recount"] = F.free_recount(df, today)
    tag_names = {int(r["tagid"]): r["name"] for r in storage.read_csv(data_dir / "tags.csv")}
    info["tag_names"] = tag_names
    info["events"] = event_data.load(events_path)
    sample = sample.join(F.event_features(sample, info["events"], tag_names))
    series = F.load_followers(gp_dir)
    sample["log_followers"] = F.prelaunch_followers(sample, series)
    sample["placebo_ok"] = F.placebo_ok(sample, data_end, PLACEBO_WEEKS)
    info["followers"] = {"games_with_series": len(series),
                         "series_in_sample": int(sample["appid"].isin(series).sum()),
                         "sample_with_value": int(sample["log_followers"].notna().sum())}
    frames = {}
    for group, free in (("paid", False), ("free", True)):
        s = sample[sample["free"] == free].copy()
        if not free:
            info["sample"]["paid_without_price"] = int((~(s["price"] > 0)).sum())
            s = s[s["price"] > 0].copy()
        pool = F.pool_of(df, free)
        s["competition"] = F.similar_counts(s, pool)
        s["comp_top5"] = F.similar_counts(s, pool, top=5)
        s["comp_top20"] = F.similar_counts(s, pool, top=20)
        s["comp_primary"] = F.similar_counts(s, pool, rule="primary")
        s["comp_placebo"] = F.similar_counts(s, pool, offset_weeks=PLACEBO_WEEKS)
        if not free:
            s["comp_tier"] = F.similar_counts(s, pool, same_tier=True)
            s["comp_tier_placebo"] = F.similar_counts(s, pool, offset_weeks=PLACEBO_WEEKS, same_tier=True)
            s["log_niche_price"] = np.log(niche_price(s, pool, info["sample"]))
            s = s[s["log_niche_price"].notna()].copy()
        add_columns(s, free)
        frames[group] = s
        info["sample"][group] = len(s)
    return frames, info


def niche_price(s: pd.DataFrame, pool: pd.DataFrame, counts: dict) -> np.ndarray:
    """The niche's median price from launches in the year before each game. Small
    niches fall back to all paid launches in that year. NaN where even that has too
    few launches (the first days of the data): those games are left out."""
    median = F.niche_median_price(s, pool)
    small = np.isnan(median)
    counts["paid_niche_median_fallback"] = int(small.sum())
    median[small] = F.market_median_price(s[small], pool)
    counts["paid_without_earlier_prices"] = int(np.isnan(median).sum())
    return median


def add_columns(s: pd.DataFrame, free: bool) -> None:
    """The numeric model columns that come straight from a game's own fields."""
    s["y"] = s["reviews_30d"]
    s["early_access"] = (s["launch_type"] == "early_access").astype(int)
    s["demo"] = s["demo"].astype(int)
    s["franchise"] = s["franchise"].astype(int)
    s["log_reach"] = np.log1p(s["reach"])
    for x in F.LANG_FLAGS:
        s[f"lang_{x}"] = [int(x in g) for g in s["langs"]]
    s["n_languages"] = [len(g) for g in s["langs"]]
    s["en_audio"] = s["en_audio"].astype(int)
    s["cn_spring_x_schinese"] = s["cn_spring"] * s["lang_schinese"]
    s["cn_national_x_schinese"] = s["cn_national"] * s["lang_schinese"]
    band = np.array([hour_band(h) for h in s["hour"]])
    for _, b in HOUR_BANDS:
        if b != HOUR_BASE:
            s[f"hour_{b}"] = (band == b).astype(int)
    for d in range(1, 7):
        s[f"dow_{d}"] = (s["dow"] == d).astype(int)
    years = [d.year for d in s["launch_date"]]
    s["year"] = years
    s["trend"] = [(d - F.SAMPLE_START).days / 365.25 for d in s["launch_date"]]
    for y in sorted(set(years))[1:]:
        s[f"year_{y}"] = [int(v == y) for v in years]
    for m in range(2, 13):
        s[f"month_{m}"] = [int(d.month == m) for d in s["launch_date"]]
    s.attrs["genres"] = top_genres(s)
    add_genres(s, s.attrs["genres"])
    if not free:
        s["log_price"] = np.log(s["price"])
        s["under_5"] = (s["price"] < 5).astype(int)
        s["revenue"] = (s["reviews_30d"] * s["price"]).round()


def top_genres(s: pd.DataFrame) -> list[int]:
    """The GENRES most common tags among the games' top 10 tags."""
    tops = pd.Series([t for pairs in s["tags"] for t, _ in pairs[:F.TOP]], dtype="int64").value_counts()
    return [int(t) for t in tops.index[:GENRES]]


def add_genres(s: pd.DataFrame, genres: list[int]) -> None:
    for t in genres:
        if f"tag_{t}" not in s:
            s[f"tag_{t}"] = [int(any(x == t for x, _ in pairs[:F.TOP])) for pairs in s["tags"]]


def hour_band(hour: int) -> str:
    return [b for h, b in HOUR_BANDS if hour >= h][-1]


def predictors(s: pd.DataFrame, free: bool, competition: str = "competition", years: str = "fe",
               followers: bool = False, genres: list[int] | None = None) -> list[str]:
    """The model's columns: `years` "fe" for year and month fixed effects, "trend" for a
    linear year trend with month effects (held-out fits, where the test year is new).
    `genres`: the tag indicators (default: the sample's most common tags)."""
    cols = [competition, "big_competitor", "attention_release", "sale", "pre_sale", "next_fest",
            "demo_last_fest", "themed_fest", "cn_spring", "cn_national", "cn_spring_x_schinese",
            "cn_national_x_schinese", "us_thanksgiving", "xmas_newyear", "early_access", "demo", "franchise",
            "log_reach", *(f"lang_{x}" for x in F.LANG_FLAGS), "n_languages", "en_audio"]
    if not free:
        cols += ["log_price", "under_5", "log_niche_price"]
    if followers:
        cols.append("log_followers")
    cols += [c for c in s.columns if c.startswith(("hour_", "dow_", "month_"))]
    cols += [f"tag_{t}" for t in (s.attrs["genres"] if genres is None else genres)]
    cols += ["trend"] if years == "trend" else [c for c in s.columns if c.startswith("year_")]
    return cols


def baseline(s: pd.DataFrame, free: bool, genres: list[int] | None = None) -> list[str]:
    """Genre, year (as a trend) and price only."""
    genres = s.attrs["genres"] if genres is None else genres
    return ["trend", *(f"tag_{t}" for t in genres)] + ([] if free else ["log_price", "under_5"])


# --- fitting ----------------------------------------------------------------

def _matrix(s: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    X = s[cols].astype(float)
    X = X.loc[:, X.std() > 0]  # a column that never varies in this sample cannot be estimated
    X.insert(0, "const", 1.0)
    return _independent(X)


def _independent(X: pd.DataFrame) -> pd.DataFrame:
    """Drop each column that is a linear combination of the ones before it (in a small
    sample a holiday can coincide with a month, say). Earlier columns win."""
    A = X.to_numpy()
    A = A / np.sqrt((A ** 2).sum(axis=0))
    G = A.T @ A
    keep: list[int] = []
    for j in range(G.shape[0]):
        resid = G[j, j]
        if keep:
            g = G[keep, j]
            resid -= g @ np.linalg.solve(G[np.ix_(keep, keep)], g)
        if resid > 1e-9:
            keep.append(j)
    return X.iloc[:, keep]


def fit_nb(s: pd.DataFrame, cols: list[str], y: str = "y", start: pd.Series | None = None):
    """Negative binomial (NB2, log link). Clustered by launch week with at least
    MIN_WEEKS weeks, else heteroskedasticity-robust (HC1) and marked preliminary.
    `start`: parameters of a similar fit to start from (by column name)."""
    import statsmodels.api as sm

    X = _matrix(s, cols)
    weeks = pd.factorize(s["week"])[0]
    robust = {"cov_type": "cluster", "cov_kwds": {"groups": weeks}} if len(set(weeks)) >= MIN_WEEKS \
        else {"cov_type": "HC1"}
    began = time.monotonic()
    model = sm.NegativeBinomial(s[y].to_numpy(dtype=float), X)
    if start is not None and set(X.columns) <= set(start.index):
        start = start.reindex([*X.columns, "alpha"]).to_numpy()
    else:
        start = _start(s[y].to_numpy(dtype=float), X)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = model.fit(start_params=start, method="newton", maxiter=100, disp=0, **robust)
        if not _ok(res):  # Newton can overshoot on very large counts (the revenue proxy)
            res = model.fit(start_params=start, method="bfgs", maxiter=5000, disp=0, **robust)
    res.preliminary = robust["cov_type"] != "cluster"
    res.n_weeks = len(set(weeks))
    if not _ok(res):
        log.warning("negative binomial fit did not converge (%s, %d games)", y, len(s))
    log.info("fitted %s on %d games, %d columns, in %.0f s", y, len(s), X.shape[1], time.monotonic() - began)
    return res


def _ok(res) -> bool:
    return (bool(res.mle_retvals.get("converged", True)) and bool(np.isfinite(res.params).all())
            and bool(np.isfinite(res.bse).all()))


def _start(y: np.ndarray, X: pd.DataFrame) -> np.ndarray:
    """Start values: least squares on log(1 + y), the intercept moved to match the mean, and alpha 1."""
    beta, *_ = np.linalg.lstsq(X.to_numpy(), np.log1p(y), rcond=None)
    mu = np.exp(X.to_numpy() @ beta)
    beta[0] += math.log(y.mean() / mu.mean()) if y.mean() > 0 else 0
    return np.append(beta, 1.0)


def fit_hurdle(s: pd.DataFrame, cols: list[str]) -> dict:
    """Hurdle check: a logit for any reviews at all, and a zero-truncated negative
    binomial for how many, given some. The truncated part starts from a plain
    negative binomial on the games with reviews (also reported, as a rough check);
    if it does not converge it is marked failed and has no effects."""
    import statsmodels.api as sm

    X = _matrix(s, cols)
    weeks = pd.factorize(s["week"])[0]
    any_ = (s["y"] > 0).to_numpy(dtype=float)
    pos = any_ > 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logit = sm.Logit(any_, X).fit(disp=0, maxiter=200, cov_type="cluster", cov_kwds={"groups": weeks})
    sp = s[pos]
    plain = fit_nb(sp, [c for c in X.columns if c != "const"])
    count, method, failure = fit_truncated_nb(sp["y"].to_numpy(dtype=float), _matrix(sp, list(X.columns[1:])),
                                              pd.factorize(sp["week"])[0], plain.params)
    part = {"n": int(pos.sum()), "converged": count is not None}
    if count is None:
        part.update(status=f"failed: {failure}; left out", failure=failure, effects=[])
    else:
        part.update(method=method, alpha=_r(float(count.params["alpha"])), effects=effects(count, sp))
    return {"any_reviews": {"n": int(len(s)), "share_with_reviews": round(float(any_.mean()), 3),
                            "effects": effects(logit, s, ratio="odds")},
            "count_given_some": part,
            "count_given_some_plain_nb": {"n": int(pos.sum()), "converged": _ok(plain),
                                          "note": "plain negative binomial on games with reviews (not truncated)",
                                          "effects": effects(plain, sp) if _ok(plain) else []}}


def fit_truncated_nb(y: np.ndarray, X: pd.DataFrame, groups: np.ndarray, start: pd.Series):
    """Zero-truncated NB2 by maximum likelihood, from `start` (a plain NB fit, alpha
    included): BFGS with the exact gradient, then Newton steps (Hessian from the
    gradient). Standard errors clustered by `groups`. Returns (result, method, None),
    or (None, None, why) when it fails: the gradient does not reach zero, alpha runs
    off past TRUNC_MAX_ALPHA (no finite maximum), or the standard errors are not finite."""
    from scipy import optimize

    A = X.to_numpy(dtype=float)
    k = A.shape[1]
    x0 = np.array(start.reindex(X.columns).fillna(0.0), dtype=float)
    x0 = np.append(x0, math.log(max(float(start.get("alpha", 1.0)), 1e-3)))  # log alpha
    n = len(y)

    def nll(theta):
        ll, _ = _truncated_nb(theta, y, A)
        return -ll.sum() / n

    def grad(theta):
        return -_truncated_nb(theta, y, A)[1].sum(axis=0) / n

    def hess(theta, h=1e-5):
        H = np.empty((k + 1, k + 1))
        for j in range(k + 1):
            e = np.zeros(k + 1)
            e[j] = h
            H[:, j] = (grad(theta + e) - grad(theta - e)) / (2 * h)
        return (H + H.T) / 2

    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        theta = optimize.minimize(nll, x0, jac=grad, method="BFGS", options={"maxiter": 2000, "gtol": 1e-7}).x
        method = "bfgs"
        for _ in range(20):
            g = grad(theta)
            if np.isfinite(g).all() and np.abs(g).max() < TRUNC_TOL:
                break
            method = "bfgs+newton"
            H = hess(theta)
            try:
                step = np.linalg.solve(H, g)
            except np.linalg.LinAlgError:
                break
            t, f0 = 1.0, nll(theta)
            while t > 1e-4 and not nll(theta - t * step) < f0:
                t /= 2
            theta = theta - t * step
        g = grad(theta)
        failure = None
        if not (np.isfinite(theta).all() and np.isfinite(g).all() and np.abs(g).max() < TRUNC_TOL):
            failure = f"did not converge (largest gradient {float(np.nanmax(np.abs(g))):.2g})"
        elif math.exp(theta[-1]) > TRUNC_MAX_ALPHA:
            failure = f"no finite maximum (alpha ran off to {math.exp(theta[-1]):.2g})"
        else:
            H = hess(theta) * n  # Hessian of the negative log-likelihood
            S = _truncated_nb(theta, y, A)[1]
            Sg = pd.DataFrame(S).groupby(groups).sum().to_numpy()
            G = Sg.shape[0]
            try:
                Hi = np.linalg.inv(H)
            except np.linalg.LinAlgError:
                Hi = np.full_like(H, np.nan)
            se = np.sqrt(np.diag(Hi @ (Sg.T @ Sg) @ Hi) * (G / (G - 1)) * ((n - 1) / (n - k - 1)))
            if not np.isfinite(se).all():
                failure = "standard errors are not finite"
    if failure:
        log.warning("truncated negative binomial failed (%d games): %s", n, failure)
        return None, None, failure
    names = [*X.columns, "alpha"]
    params = pd.Series(theta, index=names)
    params["alpha"] = math.exp(theta[-1])
    se[-1] *= params["alpha"]  # delta method: the fit was on log alpha
    return _Fitted(params, pd.Series(se, index=names)), method, None


TRUNC_TOL = 1e-6        # largest gradient (per game) that counts as converged
TRUNC_MAX_ALPHA = 100   # a larger alpha means the likelihood has no finite maximum


class _Fitted:
    """Parameters, standard errors, intervals and p-values, the parts `effects` reads."""

    def __init__(self, params: pd.Series, bse: pd.Series):
        from scipy import stats

        self.params, self.bse = params, bse
        self.pvalues = pd.Series(2 * stats.norm.sf(np.abs(params / bse)), index=params.index)

    def conf_int(self) -> pd.DataFrame:
        return pd.DataFrame({0: self.params - 1.959964 * self.bse, 1: self.params + 1.959964 * self.bse})


def _truncated_nb(theta: np.ndarray, y: np.ndarray, A: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per game: the zero-truncated NB2 log-likelihood and its gradient in (beta, log alpha)."""
    from scipy.special import digamma, gammaln

    beta, a = theta[:-1], math.exp(theta[-1])
    r = 1 / a
    mu = np.exp(A @ beta)
    am = a * mu
    l1 = np.log1p(am)
    log_p0 = -r * l1
    p0 = np.exp(log_p0)
    ll = gammaln(y + r) - gammaln(r) - gammaln(y + 1) - r * l1 + y * np.log(am) - y * l1 - np.log1p(-p0)
    odds0 = p0 / -np.expm1(log_p0)                      # p0 / (1 - p0)
    d_eta = (y - mu) / (1 + am) - odds0 * mu / (1 + am)
    d_a = (-(r * r) * (digamma(y + r) - digamma(r) - l1) - r * mu / (1 + am) + y / a - y * mu / (1 + am)
           + odds0 * ((r * r) * l1 - r * mu / (1 + am)))
    return ll, np.column_stack([A * d_eta[:, None], d_a * a])


def effects(res, s: pd.DataFrame, keys=None, ratio: str = "rate") -> list[dict]:
    """Rate (or odds) ratios with 95% intervals, for the named columns that were fitted."""
    params, ci, p = res.params, res.conf_int(), res.pvalues
    keys = keys or [k for k in params.index if k in LABELS]
    out = []
    for k in keys:
        if k not in params.index:
            continue
        scale = LOG2 if k in DOUBLING else 1.0
        row = {"key": k, "label": LABELS.get(k, k), f"{ratio}_ratio": _r(math.exp(params[k] * scale)),
               "low": _r(math.exp(ci.loc[k].iloc[0] * scale)), "high": _r(math.exp(ci.loc[k].iloc[1] * scale)),
               "p": float(f"{p[k]:.3g}")}
        values = s[k]
        if set(values.unique()) <= {0, 1}:
            row["games_with"] = int(values.sum())
            if k in CN_HOLIDAYS and f"{k}_x_schinese" in params.index:  # the effect is for games without it
                row["games_with"] -= int(s[f"{k}_x_schinese"].sum())
        else:
            row["mean"], row["median"] = _r(float(values.mean())), _r(float(values.median()))
        if k in COMPETITION:
            row["per_10"] = {"ratio": _r(math.exp(params[k] * 10)), "low": _r(math.exp(ci.loc[k].iloc[0] * 10)),
                             "high": _r(math.exp(ci.loc[k].iloc[1] * 10))}
        out.append(row)
    return out


def _r(x: float) -> float:
    return float(f"{x:.4g}")


def summary(res, s: pd.DataFrame, keys=None) -> dict:
    return {"n": int(res.nobs), "weeks": int(res.n_weeks), "games_with_reviews": int((s["y"] > 0).sum()),
            "preliminary": bool(res.preliminary), "alpha": _r(float(res.params["alpha"])),
            "effects": effects(res, s, keys)}


def held_out(s: pd.DataFrame, cols: dict[str, list[str]], y: str = "y") -> dict:
    """Fit on launches before HELD_OUT_FROM, score each model on the launches after:
    mean negative binomial log-likelihood per game (higher is better), Spearman rank
    correlation of predicted and real reviews, and mean absolute error of log(1 + reviews)."""
    from scipy import stats

    train, test = s[s["launch_date"] < HELD_OUT_FROM], s[s["launch_date"] >= HELD_OUT_FROM]
    out = {"train": int(len(train)), "test": int(len(test))}
    if len(train) < MIN_FIT or len(test) < MIN_FIT:
        return out
    yt = test[y].to_numpy(dtype=float)
    for name, c in cols.items():
        res = fit_nb(train, c, y)
        X = test.reindex(columns=[k for k in res.params.index if k != "alpha"], fill_value=0.0).astype(float)
        X["const"] = 1.0
        mu = np.exp(X.to_numpy() @ res.params.drop("alpha").to_numpy())
        a = float(res.params["alpha"])
        ll = stats.nbinom.logpmf(np.round(yt), 1 / a, 1 / (1 + a * mu))
        out[name] = {"loglik_per_game": round(float(ll.mean()), 4),
                     "spearman": round(float(stats.spearmanr(mu, yt).statistic), 4),
                     "mae_log1p": round(float(np.abs(np.log1p(mu) - np.log1p(yt)).mean()), 4)}
    return out


# --- the whole run ----------------------------------------------------------

def _competition_check(s: pd.DataFrame, free: bool, competition: str, key: str = None) -> dict:
    res = fit_nb(s, predictors(s, free, competition))
    return summary(res, s, [key or competition])


def run_group(s: pd.DataFrame, free: bool, events: list[dict] | None = None, tag_names: dict | None = None,
              permutations: int = PERMUTATIONS, recount: tuple[int, int] = (0, 0)) -> dict:
    out: dict = {}
    competition = "competition"
    # the held-out fits pick their genres from the fitting years only
    genres = top_genres(s[s["launch_date"] < HELD_OUT_FROM])
    add_genres(s, genres)
    ho_cols = {"model": predictors(s, free, years="trend", genres=genres)}
    if not free:
        ho_cols["same_tier"] = predictors(s, free, "comp_tier", years="trend", genres=genres)
    ho_cols["baseline"] = baseline(s, free, genres)
    out["held_out"] = ho = held_out(s, ho_cols)
    if "same_tier" in ho and ho["same_tier"]["loglik_per_game"] > ho["model"]["loglik_per_game"]:
        competition = "comp_tier"
    out["competition_measure"] = competition
    out["competition_chosen_by"] = "held-out log-likelihood per game" if not free else "the only measure"
    cols = predictors(s, free, competition)
    log.info("%s: main fit, %d games", "free" if free else "paid", len(s))
    main = fit_nb(s, cols)
    out["reviews"] = summary(main, s)
    # a demo that was out by the last Next Fest against no demo: the two effects add on the log scale
    out["demo_with_fest"] = combined_effect(main, s, "demo", "demo_last_fest", key="demo_with_fest")
    out["genre"] = [{"tag": int(e["key"][4:]), **e} for e in effects(main, s, [f"tag_{t}" for t in s.attrs["genres"]])]
    if not free:
        out["revenue"] = summary(fit_nb(s, cols, y="revenue", start=main.params), s)
    out["hurdle"] = fit_hurdle(s, cols)
    checks = {}
    other = "competition" if competition == "comp_tier" else ("comp_tier" if not free else None)
    for name, comp in (("top5", "comp_top5"), ("top20", "comp_top20"), ("primary_tag", "comp_primary"),
                       ("same_tier" if other == "comp_tier" else "plain", other)):
        if comp:
            checks[name] = _competition_check(s, free, comp)
    small = s[(s["reach"] <= SMALL_REACH) & (s["franchise"] == 0) & (s["launch_date"] >= F.REACH_FULL_FROM)]
    if not free:
        small = small[small["price"] < SMALL_PRICE]
    checks["small_games"] = {**summary(fit_nb(small, predictors(small, free, competition)), small,
                                       list(dict.fromkeys([competition, *KEY_EFFECTS]))),
                             "launches_from": F.REACH_FULL_FROM.isoformat()}
    checks["placebo"] = placebo_check(s[s["placebo_ok"]], free, competition)
    out["checks"] = checks
    out["followers"] = follower_fits(s, free, competition)
    if events is not None:
        out["chance_test"] = chance_tests(s, free, competition, events, tag_names or {}, permutations, main.params)
        for e in out["reviews"]["effects"]:
            t = out["chance_test"].get(e["key"])
            if t and "p_value" in t:  # the chance test's own estimate: the event alone, all games pooled
                e["chance_p"], e["chance_ratio_alone"], e["windows"] = t["p_value"], t["ratio_alone"], t["windows"]
        out["holidays"] = holiday_summary(s, out, events, main)
    out.update(group_status(s, free, recount))
    out["headline"] = "with_followers" if out["followers"].get("headline") else "reviews"
    return out


def group_status(s: pd.DataFrame, free: bool, recount: tuple[int, int] = (0, 0)) -> dict:
    """"unreliable" when most launches have no reviews, or, for free games, until at
    least FREE_RECOUNTED of them are recounted with every purchase type (PR #20).
    `recount` is (free launches, recounted) from F.free_recount: measured before the
    launches without a review count leave the sample, since a running recount blanks them."""
    zero = float((s["y"] == 0).mean()) if len(s) else 0.0
    out = {"status": "unreliable" if zero > MAX_ZERO_SHARE else "ok", "zero_share": round(zero, 4)}
    if free:
        launches, done = recount
        share = done / launches if launches else 0.0
        out["recount"] = {"launches": launches, "recounted": done}
        out["recounted_share"], out["recounted"] = round(share, 4), share >= FREE_RECOUNTED
        if not out["recounted"]:
            out["status"] = "unreliable"
    return out


def placebo_check(pl: pd.DataFrame, free: bool, competition: str) -> dict:
    """The competition measure 8 weeks after launch, built with the same rule; alone,
    the real measure on the same games, and both together."""
    placebo = PLACEBO[competition]
    return {"measure": placebo, "placebo": _competition_check(pl, free, placebo),
            "real_same_sample": _competition_check(pl, free, competition),
            "together": summary(fit_nb(pl, predictors(pl, free, competition) + [placebo]), pl,
                                [competition, placebo])}


# --- chance test for the event indicators -----------------------------------

def chance_tests(s: pd.DataFrame, free: bool, competition: str, events: list[dict], tag_names: dict,
                 draws: int, start: pd.Series | None = None, seed: int = 0) -> dict:
    """For each event indicator in PERMUTED: how often fake windows on random weeks give
    an effect at least as far from 1 as the real windows (a permutation p-value).

    The main model is refitted without the indicator (and its Simplified Chinese
    extra). Holding that fit fixed, the indicator's own coefficient is estimated
    alone (one parameter, alpha fixed), for the real windows and for `draws` sets of
    fake ones. So `ratio_alone` and the p-value are for all games pooled (for a
    Chinese holiday: with and without Simplified Chinese). Each fake set moves every
    real window by a random whole number of weeks (same length, weekday and Pacific
    clock time; themed fests keep their tags), inside the sample period, not
    overlapping any real window of the indicator or another fake one. Each indicator
    has its own random generator, seeded from `seed` and its name, so adding an
    indicator does not change the others' draws."""
    ts = s["launch_ts"].to_numpy(dtype=float)
    first, last = float(ts.min()), float(ts.max())
    y = s["y"].to_numpy(dtype=float)
    names = F.top_tag_names(s, tag_names)
    cols = predictors(s, free, competition)
    out = {"method": "refit without the indicator, then its coefficient alone against fake windows "
                     "moved by whole weeks", "draws": draws}
    for col in PERMUTED:
        windows = [w for w in F.event_windows(events, col) if w["start"] <= last and w["end"] > first]
        real = s[col].to_numpy() > 0
        if not real.any() or not windows or col not in cols:
            continue
        drop = {col, f"{col}_x_schinese"}
        base = fit_nb(s, [c for c in cols if c not in drop], start=start)
        eta = np.log(base.predict())
        alpha = float(base.params["alpha"])
        b_real = one_coefficient(y, eta, alpha, real)
        rng = np.random.default_rng([seed, zlib.crc32(col.encode())])
        fake = []
        for _ in range(draws):
            moved = move_windows(windows, rng, first, last)
            if moved is None:
                continue
            d = F.window_indicator(ts, moved, names)
            if d.any():
                fake.append(one_coefficient(y, eta, alpha, d))
        fake = np.array(fake)
        row = {"windows": len(windows), "games_with": int(real.sum()), "ratio_alone": _r(math.exp(b_real)),
               "draws_used": int(len(fake))}
        if len(fake):
            row["p_value"] = _r((1 + int((np.abs(fake) >= abs(b_real) - 1e-12).sum())) / (1 + len(fake)))
            row["fake_ratio_5_95"] = [_r(math.exp(np.quantile(fake, 0.05))), _r(math.exp(np.quantile(fake, 0.95)))]
        out[col] = row
    return out


def one_coefficient(y: np.ndarray, eta: np.ndarray, alpha: float, d: np.ndarray, steps: int = 50) -> float:
    """The NB2 coefficient of indicator `d` with the linear predictor `eta` and alpha held
    fixed (Newton on one parameter)."""
    y, eta = y[d], eta[d]
    b = 0.0
    for _ in range(steps):
        mu = np.exp(eta + b)
        score = ((y - mu) / (1 + alpha * mu)).sum()
        info = (mu * (1 + alpha * y) / (1 + alpha * mu) ** 2).sum()
        if info <= 0:
            break
        step = float(np.clip(score / info, -2, 2))
        b += step
        if abs(step) < 1e-8:
            break
    return b


def move_windows(windows: list[dict], rng: np.random.Generator, first: float, last: float,
                 tries: int = 200) -> list[dict] | None:
    """Each window moved by a random whole number of weeks into [first, last], keeping
    its Pacific clock time across daylight saving changes. A moved window never
    overlaps a real window (whatever their tags), and moved windows only clash with
    each other when their tags overlap (as the real ones may). None if no such
    placement is found."""
    week = 7 * F.DAY
    placed: list[dict] = []
    for w in windows:
        lo = math.ceil((first - w["start"]) / week) - 1   # one more week each side: the shift
        hi = math.floor((last - w["end"]) / week) + 1     # in Pacific time can move it by an hour
        for _ in range(tries):
            k = int(rng.integers(lo, hi + 1))
            m = {**w, "start": _shift(w["start"], k), "end": _shift(w["end"], k)}
            if (first <= m["start"] and m["end"] <= last and not any(_overlap(m, o) for o in windows)
                    and not any(_clash(m, o) for o in placed)):
                placed.append(m)
                break
        else:
            return None
    return placed


def _shift(ts: float, weeks: int) -> float:
    """UTC seconds `ts` moved by whole weeks at the same Pacific clock time."""
    return (datetime.fromtimestamp(ts, event_data.PACIFIC) + timedelta(weeks=weeks)).timestamp()


def _overlap(a: dict, b: dict) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def _clash(a: dict, b: dict) -> bool:
    return _overlap(a, b) and (a["tags"] is None or b["tags"] is None or bool(a["tags"] & b["tags"]))


def holiday_summary(s: pd.DataFrame, g: dict, events: list[dict], res=None) -> dict:
    """The Chinese holidays: windows in the sample and the Steam events each one
    overlapped; from the main fit `res`, the combined effect for games with Simplified
    Chinese (main effect times extra, with its own interval); and a note."""
    first, last = float(s["launch_ts"].min()), float(s["launch_ts"].max())
    steam = [w for c in ("sale", "next_fest", "themed_fest") for w in F.event_windows(events, c)]
    out: dict = {}
    for col in CN_HOLIDAYS:
        rows = []
        for w in F.event_windows(events, col):
            if w["start"] <= last and w["end"] > first:
                rows.append({"name": w["name"],
                             "overlaps": [o["name"] for o in steam if o["start"] < w["end"] and w["start"] < o["end"]]})
        out[col] = rows
    out["with_schinese"] = {} if res is None else {
        col: c for col in CN_HOLIDAYS if (c := combined_effect(res, s, col, f"{col}_x_schinese")) is not None}
    out["note"] = holiday_note(g, out)
    out["site_use"] = ("Show Chinese holidays only as calendar context for games that support Simplified Chinese, "
                       "marked unconfirmed. Not advice for other games.")
    return out


def combined_effect(res, s: pd.DataFrame, main: str, extra: str, key: str | None = None) -> dict | None:
    """The rate ratio of `main` plus `extra` (the effect for games that have both), with a
    95% interval from the fit's (clustered) covariance. None if either was not fitted.
    `key` names it (default: `main` with "_schinese", the Chinese holidays' combination)."""
    from scipy import stats

    if main not in res.params.index or extra not in res.params.index:
        return None
    key = key or f"{main}_schinese"
    V = res.cov_params()
    b = float(res.params[main] + res.params[extra])
    se = math.sqrt(float(V.loc[main, main] + V.loc[extra, extra] + 2 * V.loc[main, extra]))
    return {"key": key, "label": LABELS.get(key, main), "rate_ratio": _r(math.exp(b)),
            "low": _r(math.exp(b - 1.959964 * se)), "high": _r(math.exp(b + 1.959964 * se)),
            "p": float(f"{2 * stats.norm.sf(abs(b / se)):.3g}"), "games_with": int(s[extra].sum())}


def _effect(g: dict, key: str, part: str = "reviews") -> dict | None:
    return next((e for e in g[part]["effects"] if e["key"] == key), None)


def _ci(e: dict, ratio: str = "rate_ratio") -> str:
    return f"{e[ratio]:.2f} ({e['low']:.2f} to {e['high']:.2f})"


def _clear(e: dict) -> bool:
    return e["low"] > 1 or e["high"] < 1


def _change(e: dict) -> str:
    """'37% fewer reviews', '20% more reviews' or 'no clear difference', from the interval."""
    if not _clear(e):
        return "no clear difference"
    return f"{abs(e['rate_ratio'] - 1) * 100:.0f}% {'fewer' if e['rate_ratio'] < 1 else 'more'} reviews"


def holiday_note(g: dict, h: dict) -> str:
    """The caveat for the Chinese holidays, from the numbers. `h`: the windows per
    holiday and the combined effects for games with Simplified Chinese."""
    parts, extras, hurdle, counts, overlapped = [], [], [], [], 0
    for col, name in (("cn_spring", "Spring Festival"), ("cn_national", "National Day")):
        e, x = _effect(g, col), _effect(g, f"{col}_x_schinese")
        if e is None:
            continue
        text = f"{name}: games without Simplified Chinese {_change(e)} ({_ci(e)})"
        c = h.get("with_schinese", {}).get(col)
        if c is not None:
            text += f", games with it {_change(c)} ({_ci(c)})"
        t = g.get("chance_test", {}).get(col)
        if t and "p_value" in t:
            text += f"; the chance test (all games pooled) gives {t['ratio_alone']:.2f} with p = {t['p_value']:.2g}"
        parts.append(text)
        if x is not None:
            extras.append((name, x))
        hx = _effect(g["hurdle"], f"{col}_x_schinese", "any_reviews") if "hurdle" in g else None
        if hx is not None:
            hurdle.append((name, hx))
        counts.append(f"{len(h[col])} {name}")
        overlapped += sum(bool(w["overlaps"]) for w in h[col])
    if not parts:
        return ""
    total = sum(len(h[c]) for c in CN_HOLIDAYS)
    text = f"Chinese holidays (rate ratios, 95% intervals): {'; '.join(parts)}."
    if extras:
        listed = " and ".join(f"{_ci(x)} for {name}" for name, x in extras)
        if not any(_clear(x) for _, x in extras):
            text += (f" In the review-count model the extra effect of Simplified Chinese is {listed}: no clear "
                     "difference, but the intervals are wide, so a difference is not ruled out.")
        else:
            text += f" In the review-count model the extra effect of Simplified Chinese is {listed}."
    for name, hx in hurdle:
        if _clear(hx):
            text += (f" In the \"any reviews\" part, games with Simplified Chinese launched during {name} were "
                     f"{'less' if hx['odds_ratio'] < 1 else 'more'} likely to get any review than other games "
                     f"launched then (extra odds ratio {_ci(hx, 'odds_ratio')}).")
    text += (f" {overlapped} of the {total} holiday windows overlapped another Steam event (a sale, Next Fest or a "
             f"themed fest), and there are only {' and '.join(counts)} windows, so the week-clustered intervals "
             "overstate how sure this is. Not a general rule.")
    return text


def follower_fits(s: pd.DataFrame, free: bool, competition: str) -> dict:
    """The model with and without the follower control, on launches from FOLLOWER_FROM
    that have a follower count 7 days before launch. It becomes the headline once
    HEADLINE_COVERAGE of those launches have one, over at least HEADLINE_WEEKS weeks:
    until the backfill is done, which games have followers depends on their reviews."""
    eligible = s[s["launch_date"] >= FOLLOWER_FROM]
    f = eligible[eligible["log_followers"].notna()]
    out = {"eligible": int(len(eligible)), "games": int(len(f)), "weeks": int(f["week"].nunique()),
           "coverage": round(len(f) / len(eligible), 4) if len(eligible) else 0.0,
           "launches_from": min(f["launch_date"]).isoformat() if len(f) else None,
           "launches_to": max(f["launch_date"]).isoformat() if len(f) else None}
    if len(f) < MIN_FIT:
        out["status"] = f"not fitted: fewer than {MIN_FIT} games"
        return out
    without = fit_nb(f, predictors(f, free, competition))
    with_ = fit_nb(f, predictors(f, free, competition, followers=True))
    out["without_followers"] = summary(without, f)
    out["with_followers"] = summary(with_, f)
    b0, b1 = without.params.get(competition), with_.params.get(competition)
    if b0 is not None and b1 is not None and b0 != 0:
        out["competition_shrinks_by"] = round(1 - b1 / b0, 3)
    out["status"] = "preliminary" if with_.preliminary else "fitted"
    out["headline"] = out["coverage"] >= HEADLINE_COVERAGE and out["weeks"] >= HEADLINE_WEEKS
    return out


CAVEATS = [
    "Observational: launches in busier weeks got fewer or more reviews on average, after adjusting for the "
    "listed controls. It does not show that a busy week causes it.",
    "Pre-launch hype (wishlists, followers) drives both reviews and the choice of week. Until most launches "
    "have a follower count, the headline fit has no hype control (see followers).",
    "Reviews stand in for sales; the ratio of sales to reviews varies by genre and price.",
    "Price, demo, tags and Early Access state are today's, not launch day's.",
    "Games delisted before the data was collected are missing, so older years look a bit better than they were.",
]


FREE_CAVEAT = ("The review counts are Steam purchases only, so a free game's reviews from players who did not "
               "buy anything are left out: most free launches show 0 reviews in their first 30 days although "
               "they have reviews. Do not read the free model until free games are counted with all purchase types.")


def _per_launch(e: dict) -> str:
    """'0.9% fewer' or '1.2% more' for a per-launch rate ratio."""
    r = e["rate_ratio"]
    return f"{abs(r - 1) * 100:.1f}% {'fewer' if r < 1 else 'more'}"


def _clarity(e: dict) -> str:
    return "clear" if e["p"] < 0.01 else "at the edge of noise" if e["p"] < 0.1 else "within noise"


def placebo_caveat(check: dict) -> str | None:
    """The placebo's caveat, built from its numbers; None when the placebo alone is within noise."""
    measure, placebo = None, check["measure"]
    alone = next(iter(check["placebo"]["effects"]), None)
    real = next(iter(check["real_same_sample"]["effects"]), None)
    if alone is None or real is None or alone["low"] <= 1 <= alone["high"]:
        return None
    measure = real["key"]
    together = {e["key"]: e for e in check["together"]["effects"]}
    text = (f"Placebo: the same competition measure 8 weeks after launch goes with {_per_launch(alone)} reviews per "
            f"launch (rate ratio {alone['rate_ratio']:.3f}, {alone['low']:.3f} to {alone['high']:.3f}), against "
            f"{_per_launch(real)} for the launch week itself ({real['rate_ratio']:.3f}, {real['low']:.3f} to "
            f"{real['high']:.3f}) on the same {check['placebo']['n']:,} games.")
    same_way = (alone["rate_ratio"] < 1) == (real["rate_ratio"] < 1)
    size = abs(math.log(alone["rate_ratio"])) / max(abs(math.log(real["rate_ratio"])), 1e-12)
    if not _clear(real):
        text += (" The launch week itself shows nothing clear (within noise) while the placebo is not zero, so "
                 "this measure picks up how crowded a niche and a period are, not the week.")
    elif not same_way:
        text += " It goes the other way from the launch week's number, so the measure is not clean."
    elif size >= 0.67:
        text += (" It is about as large as the real effect or larger, so general crowding of the niche and the "
                 "period explains a lot of the competition number.")
    else:
        text += " It is smaller than the real effect, so part of the competition number is general crowding."
    t_real, t_placebo = together.get(measure), together.get(placebo)
    if t_real and t_placebo:
        text += (f" With both in one model, the launch week gives {t_real['rate_ratio']:.3f} ({t_real['low']:.3f} to "
                 f"{t_real['high']:.3f}, {_clarity(t_real)}) and the placebo {t_placebo['rate_ratio']:.3f}.")
        if t_real["p"] >= 0.01 and t_real["rate_ratio"] < 1:
            text += " So the launch week's own effect is small at most."
    return text


def group_caveats(g: dict, free: bool) -> list[str]:
    out = [FREE_CAVEAT] if free and not g.get("recounted") else []
    if not out and g.get("zero_share", 0) > MAX_ZERO_SHARE:
        out.append(f"{g['zero_share']:.0%} of these launches have no reviews in their first 30 days, too many for "
                   "the model to be read.")
    text = placebo_caveat(g["checks"]["placebo"])
    if text:
        out.append(text)
    note = g.get("holidays", {}).get("note")
    if note:
        out.append(note + " " + g["holidays"]["site_use"])
    if g["hurdle"]["count_given_some"].get("converged") is False:  # the technical reason is in its "failure"
        out.append("The hurdle model's count part (how many reviews, given at least one) has no stable fit on this "
                   "data, so it is left out. A plain count model on the games with reviews is reported instead; "
                   "it is not corrected for the missing zeros.")
    return out


def run(data_dir: Path, events_path: Path, gp_dir: Path | None, today: date | None = None,
        permutations: int = PERMUTATIONS) -> dict:
    frames, info = build_frames(data_dir, events_path, gp_dir, today)
    result = {"sample": info["sample"], "followers": info["followers"], "prelaunch_tags": info["prelaunch_tags"],
              "caveats": CAVEATS}
    for group, s in frames.items():
        free = group == "free"
        status = {"outcome": "reviews_30d", **group_status(s, free, info["free_recount"])}
        if free and not status["recounted"]:
            # a few rows, nearly all zeros, while the recount runs: not worth a fit, and the fit can crash
            log.info("free model not fitted: %d of %d free launches recounted",
                     status["recount"]["recounted"], status["recount"]["launches"])
            result[group] = {**status, "caveats": [FREE_CAVEAT]}
            continue
        log.info("fitting the %s model (%d games)", group, len(s))
        try:
            g = {"outcome": "reviews_30d", **run_group(s, free, info["events"], info["tag_names"], permutations,
                                                       info["free_recount"])}
            g["genre_names"] = {str(t): info["tag_names"].get(t) for t in s.attrs["genres"]}
            g["caveats"] = group_caveats(g, free)
        except Exception as e:  # one group's failure must not lose the other's results
            log.exception("the %s model failed", group)
            g = {**status, "status": "failed", "error": f"{type(e).__name__}: {e}"[:300]}
        result[group] = g
    return result


def report(result: dict) -> str:
    """The main numbers as readable lines."""
    lines = [f"sample: {result['sample']}", f"followers: {result['followers']}"]
    for group in ("paid", "free"):
        g = result[group]
        recount = (f" (recounted {g['recount']['recounted']} of {g['recount']['launches']}, "
                   f"{g['recounted_share']:.1%})" if "recount" in g else "")
        if "reviews" not in g:  # not fitted, or failed
            lines.append(f"\n== {group}: not fitted, status {g['status']}{recount}"
                         + (f": {g['error']}" if "error" in g else ""))
            lines.extend(f"  caveat: {c}" for c in g.get("caveats", []))
            continue
        lines.append(f"\n== {group}: {g['reviews']['n']} games, {g['reviews']['weeks']} weeks, "
                     f"competition measure {g['competition_measure']}, status {g['status']}{recount}")
        for e in g["reviews"]["effects"]:
            chance = (f"  chance p {e['chance_p']} ({e['windows']} windows; alone, all games {e['chance_ratio_alone']})"
                      if "chance_p" in e else "")
            lines.append(f"  {e['key']:24s} {e['rate_ratio']:.3f} [{e['low']:.3f}, {e['high']:.3f}]"
                         f"  {e.get('games_with', e.get('mean'))}{chance}")
        if "revenue" in g:
            lines.append("  revenue: " + _brief(g["revenue"]["effects"]))
        if g.get("demo_with_fest"):
            d = g["demo_with_fest"]
            lines.append(f"  demo out by the last Next Fest, against no demo: {d['rate_ratio']:.3f} "
                         f"[{d['low']:.3f}, {d['high']:.3f}]")
        if g.get("holidays", {}).get("with_schinese"):
            lines.append("  holidays, games with Simplified Chinese: "
                         + _brief(list(g["holidays"]["with_schinese"].values())))
        lines.append("  hurdle any: " + _brief(g["hurdle"]["any_reviews"]["effects"], "odds_ratio"))
        count = g["hurdle"]["count_given_some"]
        lines.append(f"  hurdle count (converged {count['converged']}): " + _brief(count["effects"]))
        plain = g["hurdle"]["count_given_some_plain_nb"]
        lines.append("  plain NB on games with reviews: " + _brief(plain["effects"]))
        for name, c in g["checks"].items():
            if name == "placebo":
                lines.append(f"  placebo {c['measure']} (n {c['placebo']['n']}): {_brief(c['placebo']['effects'])}"
                             f" | real: {_brief(c['real_same_sample']['effects'])}"
                             f" | together: {_brief(c['together']['effects'])}")
            else:
                lines.append(f"  {name} (n {c['n']}): {_brief(c['effects'])}")
        lines.append(f"  held out: {g['held_out']}")
        if "chance_test" in g:
            lines.append(f"  chance test: {g['chance_test']}")
        fo = g["followers"]
        lines.append(f"  followers: {', '.join(f'{k} {v}' for k, v in fo.items() if not isinstance(v, dict))}")
        for name in ("without_followers", "with_followers"):
            if name in fo:
                lines.append(f"    {name} (n {fo[name]['n']}, weeks {fo[name]['weeks']}): "
                             f"{_brief(fo[name]['effects'])}")
        lines.extend(f"  caveat: {c}" for c in g["caveats"])
    return "\n".join(lines)


def _brief(effects: list[dict], ratio: str = "rate_ratio") -> str:
    return ", ".join(f"{e['key']} {e[ratio]:.3f} [{e['low']:.3f}, {e['high']:.3f}]" for e in effects
                     if e["key"] in KEY_EFFECTS or e["key"] in COMPETITION or e["key"] == "log_followers"
                     or e["key"].startswith("cn_"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("_data"))
    p.add_argument("--gp-dir", type=Path, default=None,
                   help="Games Popularity folder (followers/*.csv.gz); without it, no follower control")
    p.add_argument("--events", type=Path, default=Path("data/events.yaml"))
    p.add_argument("--out", type=Path, default=Path("site/public/data"))
    p.add_argument("--today", type=date.fromisoformat, default=None,
                   help="the data's date (default: the newest launch date in history); later launches are ignored")
    p.add_argument("--permutations", type=int, default=PERMUTATIONS,
                   help="fake window sets per event indicator in the chance test (default %(default)s)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.out.resolve() == args.data_dir.resolve():
        raise SystemExit("--out must not be the data folder")
    result = run(args.data_dir, args.events, args.gp_dir, args.today, args.permutations)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "model.json").write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False),
                                         encoding="utf-8")
    print(report(result))
    # a failed paid model fails the run, so the workflow does not commit it; a failed free one
    # alone does not (the free model is not read yet, and the site uses the paid results)
    return 1 if result["paid"]["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
