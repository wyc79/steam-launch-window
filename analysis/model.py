"""What history says: the launch model (docs/phase2-plan.md section 3).

    python -m analysis.model --data-dir _data --gp-dir _gp --out site/data

Fits negative binomial models (log link) of 30-day reviews on niche
competition, Steam events, price and the other predictors in
`analysis.features`, separately for paid and free games, with standard errors
clustered by launch week. Writes model.json (effects as rate ratios with 95%
intervals, sample sizes, checks, caveats) and prints a summary.

Checks: a hurdle model; the revenue proxy (reviews x price, paid games);
small games only; a placebo (competition 8 weeks after launch); top 5 and
top 20 tags; the same primary tag; same price tier; with and without the
pre-launch follower control; and 2026 launches held out against a baseline of
genre, year and price.

Needs the `analysis` extra (pandas, statsmodels). Reads only local files.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import events as event_data
from pipeline import storage

from . import features as F

GENRES = 30
HELD_OUT_FROM = date(2026, 1, 1)
PLACEBO_WEEKS = 8
SMALL_PRICE = 20        # small games: under $20, no franchise, publisher with at most 2 earlier launches
SMALL_REACH = 2
MIN_FIT = 100           # fewer games: a model is not fitted
MIN_WEEKS = 20          # fewer launch weeks: no clustering, and the result is marked preliminary
FOLLOWER_FROM = date(2024, 6, 1)  # follower history starts 2024-03-15
HEADLINE_COVERAGE = 0.9  # the follower-controlled fit leads once this share of eligible launches have followers
HEADLINE_WEEKS = 52
MAX_ZERO_SHARE = 0.8     # a group where more launches than this have no reviews is marked unreliable
HOUR_BANDS = ((0, "0_5"), (6, "6_9"), (10, "10_12"), (13, "13_17"), (18, "18_23"))
HOUR_BASE = "10_12"
COMPETITION = ("competition", "comp_tier", "comp_top5", "comp_top20", "comp_primary", "comp_placebo")
LOG2 = math.log(2)

LABELS = {
    "competition": "one more launch in the same niche that week",
    "comp_tier": "one more launch in the same niche and price tier that week",
    "comp_top5": "one more same-niche launch that week (niche from the top 5 tags)",
    "comp_top20": "one more same-niche launch that week (niche from the top 20 tags)",
    "comp_primary": "one more launch with the same primary tag that week",
    "comp_placebo": "one more same-niche launch 8 weeks after launch (placebo)",
    "big_competitor": "a big paid release on Steam within 3 days",
    "attention_release": "a big free-to-play or console-only release within 3 days",
    "sale": "launch during a seasonal sale",
    "pre_sale": "launch in the 7 days before a seasonal sale",
    "next_fest": "launch during Next Fest",
    "demo_last_fest": "demo out during the last Next Fest before launch",
    "themed_fest": "launch during a themed fest for one of its top tags",
    "cn_spring": "launch during China's Spring Festival holiday",
    "cn_national": "launch during China's National Day holiday",
    "cn_spring_x_schinese": "Spring Festival launch with Simplified Chinese (extra, on top)",
    "cn_national_x_schinese": "National Day launch with Simplified Chinese (extra, on top)",
    "us_thanksgiving": "launch between US Thanksgiving and Cyber Monday",
    "xmas_newyear": "launch between Christmas and New Year",
    "early_access": "Early Access launch",
    "demo": "had a demo before launch",
    "franchise": "part of a franchise",
    "log_reach": "publisher's earlier launches, per doubling (of 1 + count)",
    "log_price": "price, per doubling",
    "under_5": "price under $5",
    "price_vs_niche": "price against the niche's median price, per doubling",
    "n_languages": "one more supported language",
    "en_audio": "English audio",
    "log_followers": "pre-launch followers, per doubling (of 1 + count)",
    **{f"lang_{x}": f"supports {x}" for x in F.LANG_FLAGS},
    **{f"hour_{b}": f"launch hour {b.replace('_', ' to ')} Pacific (against 10 to 12)" for _, b in HOUR_BANDS
       if b != HOUR_BASE},
}
DOUBLING = {"log_reach", "log_price", "price_vs_niche", "log_followers"}
KEY_EFFECTS = ("competition", "big_competitor", "sale", "pre_sale", "next_fest", "demo_last_fest", "themed_fest",
               "cn_spring", "cn_national", "us_thanksgiving", "xmas_newyear", "early_access", "demo",
               "log_price", "under_5", "price_vs_niche")

log = logging.getLogger("model")


# --- data -------------------------------------------------------------------

def build_frames(data_dir: Path, events_path: Path, gp_dir: Path | None = None,
                 today: date | None = None) -> tuple[dict[str, pd.DataFrame], dict]:
    """The paid and free model frames, with every predictor, and counts for the report."""
    df = F.load_history(data_dir / "history" / "games.csv")
    info = {"prelaunch_tags": F.prelaunch_tags(df, data_dir / "upcoming" / "apps.csv")}
    data_end = max(df["launch_date"])
    today = today or data_end
    df["reach"] = F.publisher_reach(df)
    sample, counts = F.sample(df, today)
    info["sample"] = counts
    tag_names = {int(r["tagid"]): r["name"] for r in storage.read_csv(data_dir / "tags.csv")}
    info["tag_names"] = tag_names
    sample = sample.join(F.event_features(sample, event_data.load(events_path), tag_names))
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
            median = F.niche_median_price(s, pool)
            info["sample"]["paid_niche_median_fallback"] = int(np.isnan(median).sum())
            median = np.where(np.isnan(median), np.median(pool["price"][pool["price"] > 0]), median)
            s["price_vs_niche"] = np.log(s["price"].to_numpy() / median)
        add_columns(s, free)
        frames[group] = s
        info["sample"][group] = len(s)
    return frames, info


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
    tops = pd.Series([t for pairs in s["tags"] for t, _ in pairs[:F.TOP]]).value_counts()
    s.attrs["genres"] = [int(t) for t in tops.index[:GENRES]]
    for t in s.attrs["genres"]:
        s[f"tag_{t}"] = [int(any(x == t for x, _ in pairs[:F.TOP])) for pairs in s["tags"]]
    if not free:
        s["log_price"] = np.log(s["price"])
        s["under_5"] = (s["price"] < 5).astype(int)
        s["revenue"] = (s["reviews_30d"] * s["price"]).round()


def hour_band(hour: int) -> str:
    return [b for h, b in HOUR_BANDS if hour >= h][-1]


def predictors(s: pd.DataFrame, free: bool, competition: str = "competition", years: str = "fe",
               followers: bool = False) -> list[str]:
    """The model's columns: `years` "fe" for year and month fixed effects, "trend" for a
    linear year trend with month effects (held-out fits, where the test year is new)."""
    cols = [competition, "big_competitor", "attention_release", "sale", "pre_sale", "next_fest",
            "demo_last_fest", "themed_fest", "cn_spring", "cn_national", "cn_spring_x_schinese",
            "cn_national_x_schinese", "us_thanksgiving", "xmas_newyear", "early_access", "demo", "franchise",
            "log_reach", *(f"lang_{x}" for x in F.LANG_FLAGS), "n_languages", "en_audio"]
    if not free:
        cols += ["log_price", "under_5", "price_vs_niche"]
    if followers:
        cols.append("log_followers")
    cols += [c for c in s.columns if c.startswith(("hour_", "dow_", "month_"))]
    cols += [f"tag_{t}" for t in s.attrs["genres"]]
    cols += ["trend"] if years == "trend" else [c for c in s.columns if c.startswith("year_")]
    return cols


def baseline(s: pd.DataFrame, free: bool) -> list[str]:
    """Genre, year (as a trend) and price only."""
    return ["trend", *(f"tag_{t}" for t in s.attrs["genres"])] + ([] if free else ["log_price", "under_5"])


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


def fit_nb(s: pd.DataFrame, cols: list[str], y: str = "y"):
    """Negative binomial (NB2, log link). Clustered by launch week with at least
    MIN_WEEKS weeks, else heteroskedasticity-robust (HC1) and marked preliminary."""
    import statsmodels.api as sm

    X = _matrix(s, cols)
    weeks = pd.factorize(s["week"])[0]
    robust = {"cov_type": "cluster", "cov_kwds": {"groups": weeks}} if len(set(weeks)) >= MIN_WEEKS \
        else {"cov_type": "HC1"}
    began = time.monotonic()
    model = sm.NegativeBinomial(s[y].to_numpy(dtype=float), X)
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
    return bool(res.mle_retvals.get("converged", True)) and bool(np.isfinite(res.params).all())         and bool(np.isfinite(res.bse).all())


def _start(y: np.ndarray, X: pd.DataFrame) -> np.ndarray:
    """Start values: least squares on log(1 + y), the intercept moved to match the mean, and alpha 1."""
    beta, *_ = np.linalg.lstsq(X.to_numpy(), np.log1p(y), rcond=None)
    mu = np.exp(X.to_numpy() @ beta)
    beta[0] += math.log(y.mean() / mu.mean()) if y.mean() > 0 else 0
    return np.append(beta, 1.0)


def fit_hurdle(s: pd.DataFrame, cols: list[str]) -> dict:
    """Hurdle check: a logit for any reviews at all, and a zero-truncated negative
    binomial for how many, given some."""
    import statsmodels.api as sm
    from statsmodels.discrete.truncated_model import TruncatedLFNegativeBinomialP

    X = _matrix(s, cols)
    weeks = pd.factorize(s["week"])[0]
    any_ = (s["y"] > 0).to_numpy(dtype=float)
    pos = any_ > 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logit = sm.Logit(any_, X).fit(disp=0, maxiter=200, cov_type="cluster", cov_kwds={"groups": weeks})
        Xp = X[pos].loc[:, X[pos].std() > 0].copy()
        Xp.insert(0, "const", 1.0)
        yp = s["y"].to_numpy(dtype=float)[pos]
        start = _start(yp, Xp)
        count = TruncatedLFNegativeBinomialP(yp, Xp, truncation=0, p=2).fit(
            start_params=start, method="bfgs", maxiter=3000, disp=0, cov_type="cluster",
            cov_kwds={"groups": weeks[pos]})
    return {"any_reviews": {"n": int(len(s)), "share_with_reviews": round(float(any_.mean()), 3),
                            "effects": effects(logit, s, ratio="odds")},
            "count_given_some": {"n": int(pos.sum()), "effects": effects(count, s[pos])}}


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


def run_group(s: pd.DataFrame, free: bool) -> dict:
    out: dict = {}
    competition = "competition"
    if not free:
        trend = {"model": predictors(s, free, years="trend"),
                 "same_tier": predictors(s, free, "comp_tier", years="trend"),
                 "baseline": baseline(s, free)}
        out["held_out"] = held_out(s, trend)
        ho = out["held_out"]
        if "same_tier" in ho and ho["same_tier"]["loglik_per_game"] > ho["model"]["loglik_per_game"]:
            competition = "comp_tier"
        out["competition_measure"] = competition
    else:
        out["held_out"] = held_out(s, {"model": predictors(s, free, years="trend"), "baseline": baseline(s, free)})
        out["competition_measure"] = competition
    cols = predictors(s, free, competition)
    log.info("%s: main fit, %d games", "free" if free else "paid", len(s))
    main = fit_nb(s, cols)
    out["reviews"] = summary(main, s)
    out["genre"] = [{"tag": int(e["key"][4:]), **e} for e in effects(main, s, [f"tag_{t}" for t in s.attrs["genres"]])]
    if not free:
        out["revenue"] = summary(fit_nb(s, cols, y="revenue"), s)
    out["hurdle"] = fit_hurdle(s, cols)
    checks = {}
    other = "competition" if competition == "comp_tier" else ("comp_tier" if not free else None)
    for name, comp in (("top5", "comp_top5"), ("top20", "comp_top20"), ("primary_tag", "comp_primary"),
                       ("same_tier" if other == "comp_tier" else "plain", other)):
        if comp:
            checks[name] = _competition_check(s, free, comp)
    small = s[(s["reach"] <= SMALL_REACH) & (s["franchise"] == 0)]
    if not free:
        small = small[small["price"] < SMALL_PRICE]
    checks["small_games"] = summary(fit_nb(small, predictors(small, free, competition)), small,
                                    list(dict.fromkeys([competition, *KEY_EFFECTS])))
    pl = s[s["placebo_ok"]]
    checks["placebo"] = {"placebo": _competition_check(pl, free, "comp_placebo"),
                         "real_same_sample": _competition_check(pl, free, competition),
                         "together": summary(fit_nb(pl, predictors(pl, free, competition) + ["comp_placebo"]), pl,
                                             [competition, "comp_placebo"])}
    out["checks"] = checks
    out["followers"] = follower_fits(s, free, competition)
    zero = float((s["y"] == 0).mean())
    out["status"] = "unreliable" if zero > MAX_ZERO_SHARE else "ok"
    out["headline"] = "with_followers" if out["followers"].get("headline") else "reviews"
    return out


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
PLACEBO_CAVEAT = ("The placebo (same-niche launches 8 weeks after launch) goes with fewer reviews too, about as "
                  "much as the launch week's own competition. So the competition number mostly reflects how "
                  "crowded the niche and the period are in general, not the chosen week.")


def group_caveats(g: dict, free: bool) -> list[str]:
    out = [FREE_CAVEAT] if free and g["status"] == "unreliable" else []
    placebo = g["checks"]["placebo"]["placebo"]["effects"]
    if placebo and (placebo[0]["high"] < 1 or placebo[0]["low"] > 1):
        out.append(PLACEBO_CAVEAT)
    return out


def run(data_dir: Path, events_path: Path, gp_dir: Path | None, today: date | None = None) -> dict:
    frames, info = build_frames(data_dir, events_path, gp_dir, today)
    result = {"sample": info["sample"], "followers": info["followers"], "prelaunch_tags": info["prelaunch_tags"],
              "caveats": CAVEATS}
    for group, s in frames.items():
        log.info("fitting the %s model (%d games)", group, len(s))
        result[group] = {"outcome": "reviews_30d", **run_group(s, group == "free")}
        result[group]["genre_names"] = {str(t): info["tag_names"].get(t) for t in s.attrs["genres"]}
        result[group]["caveats"] = group_caveats(result[group], group == "free")
    return result


def report(result: dict) -> str:
    """The main numbers as readable lines."""
    lines = [f"sample: {result['sample']}", f"followers: {result['followers']}"]
    for group in ("paid", "free"):
        g = result[group]
        lines.append(f"\n== {group}: {g['reviews']['n']} games, {g['reviews']['weeks']} weeks, "
                     f"competition measure {g['competition_measure']}")
        for e in g["reviews"]["effects"]:
            lines.append(f"  {e['key']:24s} {e['rate_ratio']:.3f} [{e['low']:.3f}, {e['high']:.3f}]"
                         f"  {e.get('games_with', e.get('mean'))}")
        if "revenue" in g:
            lines.append("  revenue: " + _brief(g["revenue"]["effects"]))
        lines.append("  hurdle any: " + _brief(g["hurdle"]["any_reviews"]["effects"], "odds_ratio"))
        lines.append("  hurdle count: " + _brief(g["hurdle"]["count_given_some"]["effects"]))
        for name, c in g["checks"].items():
            if name == "placebo":
                lines.append(f"  placebo (n {c['placebo']['n']}): {_brief(c['placebo']['effects'])} | real: "
                             f"{_brief(c['real_same_sample']['effects'])} | together: {_brief(c['together']['effects'])}")
            else:
                lines.append(f"  {name} (n {c['n']}): {_brief(c['effects'])}")
        lines.append(f"  held out: {g['held_out']}")
        fo = g["followers"]
        lines.append(f"  followers: {', '.join(f'{k} {v}' for k, v in fo.items() if not isinstance(v, dict))}")
        for name in ("without_followers", "with_followers"):
            if name in fo:
                lines.append(f"    {name} (n {fo[name]['n']}, weeks {fo[name]['weeks']}): {_brief(fo[name]['effects'])}")
        lines.extend(f"  caveat: {c}" for c in g["caveats"])
    return "\n".join(lines)


def _brief(effects: list[dict], ratio: str = "rate_ratio") -> str:
    return ", ".join(f"{e['key']} {e[ratio]:.3f} [{e['low']:.3f}, {e['high']:.3f}]" for e in effects
                     if e["key"] in KEY_EFFECTS or e["key"] in COMPETITION or e["key"] == "log_followers")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("_data"))
    p.add_argument("--gp-dir", type=Path, default=None,
                   help="Games Popularity folder (followers/*.csv.gz); without it, no follower control")
    p.add_argument("--events", type=Path, default=Path("data/events.yaml"))
    p.add_argument("--out", type=Path, default=Path("site/data"))
    p.add_argument("--today", type=date.fromisoformat, default=None,
                   help="the data's date (default: the newest launch date in history)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.out.resolve() == args.data_dir.resolve():
        raise SystemExit("--out must not be the data folder")
    result = run(args.data_dir, args.events, args.gp_dir, args.today)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "model.json").write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False),
                                         encoding="utf-8")
    print(report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
