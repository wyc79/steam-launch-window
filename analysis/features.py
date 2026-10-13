"""Predictors for the launch model (docs/phase2-plan.md section 3).

Every launch gets one row. The main pieces:

- Niche competition: other launches (full or Early Access, same group: paid
  with paid, free with free) in the same Monday-to-Sunday week whose top tags
  have a tag-weight cosine similarity of at least 0.3 with the game's and that
  share a major language with it. Variants: top 5 or 20 tags, the same primary
  tag, the same price tier, or another week (the placebo).
- Steam events from events.yaml, with the windows of `pipeline.events.window`
  (Steam events run 10:00 to 10:00 Pacific; holidays cover whole days).
- The niche's price: the median price of the paid launches in the game's niche
  in the year before it (earlier launches only).
- Pre-launch followers: Games Popularity's count 7 days before launch,
  interpolated between the nearest observations.

Needs pandas, numpy and scipy (the `analysis` extra). Reads only local files.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from pipeline import events as event_data
from pipeline import storage

from .heatmap import PANEL_TYPES
from .site_data import is_free

SAMPLE_START = date(2022, 1, 1)
REACH_FULL_FROM = date(2023, 1, 1)  # publisher reach has a full year of history behind it from here
GAP_DAYS = 31           # the 30-day review window must have closed
SIMILAR = 0.3           # cosine similarity that counts as the same niche
SIMILAR_TOL = 1e-9      # rounding slack for that comparison (cosines are float64 everywhere)
TOP = 10
LANG_FLAGS = ("schinese", "japanese", "russian", "korean", "brazilian", "german", "french", "spanish")
MAJOR_LANGUAGES = ("english", *LANG_FLAGS)
NEAR_DAYS = 3           # a big release this many days from launch counts as nearby
PRE_SALE_DAYS = 7
FOLLOWER_DAYS = 7       # followers are read this many days before launch
ONE_SIDED_DAYS = 2      # without observations on both sides, the nearest one counts only this close
MIN_NICHE = 5           # fewer other games in the niche: compare with the median of all paid games
PRICE_DAYS = 365        # niche prices come from launches in this many days before the game
TIERS = (10, 25)        # price tiers: under $10, $10 to $25, over $25
HOLIDAYS = {"China Spring Festival holiday": "cn_spring", "China National Day holiday": "cn_national",
            "US Thanksgiving to Cyber Monday": "us_thanksgiving", "Christmas to New Year": "xmas_newyear"}
EVENT_COLUMNS = ("sale", "pre_sale", "next_fest", "demo_last_fest", "themed_fest", "big_competitor",
                 "attention_release", *HOLIDAYS.values())
DAY = 86400


def parse_tags(raw: str) -> list[tuple[int, int]]:
    """'id:weight|...' as (id, weight) pairs, heaviest first (ties by id)."""
    pairs = [(int(t), int(w or 0)) for t, _, w in (p.partition(":") for p in (raw or "").split("|") if p)]
    return sorted(pairs, key=lambda p: (-p[1], p[0]))


def _split(raw: str) -> list[str]:
    return [x for x in (raw or "").split("|") if x]


def load_history(path: Path) -> pd.DataFrame:
    """history/games.csv as one row per launch, with parsed fields."""
    rows = []
    for r in storage.read_csv(path):
        tags = parse_tags(r["tags"])
        rows.append({
            "appid": int(r["appid"]), "launch_date": date.fromisoformat(r["launch_date"]),
            "launch_ts": int(r["launch_ts"]), "launch_type": r["launch_type"], "tags": tags,
            "free": is_free(r["is_free"], [t for t, _ in tags]),
            "price": int(r["price_cents"]) / 100 if r["price_cents"] else math.nan,
            "langs": frozenset(_split(r["languages"])), "en_audio": "english" in _split(r["audio_languages"]),
            "demo": r["demo_before_launch"] == "1",
            "demo_ts": float(r["demo_release_ts"]) if r["demo_release_ts"] else math.nan,
            "publishers": _split(r["publishers"]), "franchise": bool(r["franchises"]),
            "reviews_30d": float(r["reviews_30d"]) if r["reviews_30d"] != "" else math.nan,
            "source": r["reviews_30d_source"],
            "purchase": r.get("reviews_purchase", ""),  # "all" once recounted; files from before PR #20 lack it
        })
    df = pd.DataFrame(rows)
    df["week"] = [d - timedelta(days=d.weekday()) for d in df["launch_date"]]
    at = pd.to_datetime(df["launch_ts"], unit="s", utc=True).dt.tz_convert(event_data.PACIFIC)
    df["hour"] = at.dt.hour
    df["dow"] = [d.weekday() for d in df["launch_date"]]
    return df


def prelaunch_tags(df: pd.DataFrame, apps_path: Path) -> int:
    """Use the frozen pre-launch tags from upcoming/apps.csv where the game was last
    seen there before its launch (tags keep being voted after launch). Changes `df`
    in place and returns how many games got them."""
    if not Path(apps_path).exists():
        return 0
    frozen = {int(r["appid"]): (date.fromisoformat(r["last_seen"]), parse_tags(r["tags"]))
              for r in storage.read_csv(apps_path) if r["tags"] and r["last_seen"]}
    n = 0
    for i, (appid, launch) in enumerate(zip(df["appid"], df["launch_date"])):
        hit = frozen.get(appid)
        if hit and hit[0] < launch:
            df.at[df.index[i], "tags"] = hit[1]
            n += 1
    return n


def sample(df: pd.DataFrame, today: date) -> tuple[pd.DataFrame, dict]:
    """Launches in the model and how many each rule left out: 2022-01-01 until
    GAP_DAYS before `today`, full and Early Access (not ea_exit), with a review
    count (not `unavailable`). Launches on Jan 1 and 2, 2022 are left out too:
    their week started in 2021, before the data, so its competition is not known."""
    counts = {"history_rows": len(df), "sample_end": (today - timedelta(days=GAP_DAYS)).isoformat()}
    keep = _in_period(df, today)
    counts["in_period"] = int(keep.sum())
    for name, out in _left_out(df):
        counts[name] = int((keep & out).sum())
        keep &= ~out
    counts["kept"] = int(keep.sum())
    return df[keep].copy(), counts


def _in_period(df: pd.DataFrame, today: date) -> pd.Series:
    return (df["launch_date"] >= SAMPLE_START) & (df["launch_date"] <= today - timedelta(days=GAP_DAYS))


def _left_out(df: pd.DataFrame) -> tuple[tuple[str, pd.Series], ...]:
    """The sample's rules, in order: (name, launches it leaves out)."""
    return (("ea_exit", df["launch_type"] == "ea_exit"),
            ("unavailable_reviews", df["source"] == "unavailable"),
            ("no_review_count", df["reviews_30d"].isna()),
            ("week_before_data", df["week"] < SAMPLE_START))


def free_recount(df: pd.DataFrame, today: date) -> tuple[int, int]:
    """Free launches the sample takes, or would take with a review count, and how many
    are recounted: reviews_purchase "all" and a 30-day count. A recount marks every free
    row "all" when it starts and blanks the counts it redoes, so a row is done only once
    its count is back, and rows still waiting stay in the total."""
    keep = _in_period(df, today) & df["free"]
    for name, out in _left_out(df):
        if name != "no_review_count":
            keep &= ~out
    done = keep & (df["purchase"] == "all") & df["reviews_30d"].notna()
    return int(keep.sum()), int(done.sum())


def tag_vectors(tags, top: int, index: dict[int, int]) -> sparse.csr_matrix:
    """Each game's top `top` tags as an L2-normalized row of vote weights."""
    rows, cols, vals = [], [], []
    for i, pairs in enumerate(tags):
        chosen = [(t, w) for t, w in pairs[:top] if w > 0]
        norm = math.sqrt(sum(w * w for _, w in chosen)) or 1.0
        for t, w in chosen:
            rows.append(i)
            cols.append(index[t])
            vals.append(w / norm)
    return sparse.csr_matrix((vals, (rows, cols)), shape=(len(tags), len(index)), dtype=np.float64)


def lang_matrix(langs) -> np.ndarray:
    return np.array([[x in g for x in MAJOR_LANGUAGES] for g in langs], dtype=np.float32).reshape(-1, len(MAJOR_LANGUAGES))


def tier(price: float) -> int:
    """0 under $10, 1 for $10 to $25, 2 over $25, -1 without a price."""
    if not price > 0:
        return -1
    return 0 if price < TIERS[0] else 1 if price <= TIERS[1] else 2


def _index(*frames) -> dict[int, int]:
    return {t: i for i, t in enumerate(sorted({t for f in frames for pairs in f["tags"] for t, _ in pairs}))}


def similar_counts(targets: pd.DataFrame, pool: pd.DataFrame, top: int = TOP, threshold: float = SIMILAR,
                   offset_weeks: int = 0, rule: str = "cosine", same_tier: bool = False) -> np.ndarray:
    """For each target, how many pool games launched in the target's week (moved by
    `offset_weeks`) are in its niche and share a major language with it, not
    counting the game itself. rule "cosine": tag-weight cosine of the top `top`
    tags at least `threshold`; rule "primary": the same top tag. `same_tier`
    also needs the same price tier."""
    index = _index(targets, pool)
    tv, pv = tag_vectors(list(targets["tags"]), top, index), tag_vectors(list(pool["tags"]), top, index)
    tl, pl = lang_matrix(targets["langs"]), lang_matrix(pool["langs"])
    t_app, p_app = targets["appid"].to_numpy(), pool["appid"].to_numpy()
    t_first = np.array([p[0][0] if p else -1 for p in targets["tags"]])
    p_first = np.array([p[0][0] if p else -2 for p in pool["tags"]])
    t_tier = np.array([tier(p) for p in targets["price"]])
    p_tier = np.array([tier(p) for p in pool["price"]])
    by_week: dict[date, list[int]] = {}
    for j, w in enumerate(pool["week"]):
        by_week.setdefault(w, []).append(j)
    target_weeks: dict[date, list[int]] = {}
    for i, w in enumerate(targets["week"]):
        target_weeks.setdefault(w + timedelta(weeks=offset_weeks), []).append(i)
    out = np.zeros(len(targets), dtype=np.int64)
    for week, ti in target_weeks.items():
        pj = by_week.get(week)
        if not pj:
            continue
        ti, pj = np.array(ti), np.array(pj)
        if rule == "cosine":
            ok = (tv[ti] @ pv[pj].T).toarray() >= threshold - SIMILAR_TOL
        elif rule == "primary":
            ok = t_first[ti][:, None] == p_first[pj][None, :]
        else:
            raise ValueError(f"unknown rule {rule!r}")
        ok &= (tl[ti] @ pl[pj].T) > 0
        ok &= t_app[ti][:, None] != p_app[pj][None, :]
        if same_tier:
            ok &= (t_tier[ti][:, None] == p_tier[pj][None, :]) & (t_tier[ti][:, None] >= 0)
        out[ti] = ok.sum(axis=1)
    return out


def _price_window(targets: pd.DataFrame, days: int) -> tuple[np.ndarray, np.ndarray]:
    """Per target, the [start, end) launch times (UTC seconds) of the pool games that count
    for its price comparison: launched in the `days` before it."""
    t_ts = targets["launch_ts"].to_numpy(dtype=np.int64)
    return t_ts - days * DAY, t_ts


def niche_median_price(targets: pd.DataFrame, pool: pd.DataFrame, top: int = TOP, threshold: float = SIMILAR,
                       days: int = PRICE_DAYS, chunk: int = 250) -> np.ndarray:
    """Median price of the paid pool games in each target's niche (same cosine and
    language rule as `similar_counts`) that launched in the `days` before it, so no
    later launch is used. NaN with fewer than MIN_NICHE."""
    pool = pool[pool["price"] > 0]
    order = np.argsort(pool["price"].to_numpy(), kind="stable")
    pool = pool.iloc[order]
    prices = pool["price"].to_numpy()
    p_ts = pool["launch_ts"].to_numpy(dtype=np.int64)
    lo_ts, hi_ts = _price_window(targets, days)
    index = _index(targets, pool)
    tv = tag_vectors(list(targets["tags"]), top, index)
    pv = tag_vectors(list(pool["tags"]), top, index).T.toarray()
    tl, pl = lang_matrix(targets["langs"]), lang_matrix(pool["langs"]).T
    t_app, p_app = targets["appid"].to_numpy(), pool["appid"].to_numpy()
    out = np.full(len(targets), np.nan)
    for start in range(0, len(targets), chunk):
        s = slice(start, start + chunk)
        ok = (tv[s] @ pv >= threshold - SIMILAR_TOL) & (tl[s] @ pl > 0) & (t_app[s][:, None] != p_app[None, :])
        ok &= (p_ts[None, :] >= lo_ts[s][:, None]) & (p_ts[None, :] < hi_ts[s][:, None])
        out[s] = _sorted_median(ok, prices)
    return out


def _sorted_median(ok: np.ndarray, prices: np.ndarray) -> np.ndarray:
    """Row-wise median of `prices` (sorted ascending) where `ok`; NaN with fewer than MIN_NICHE."""
    run = np.cumsum(ok, axis=1, dtype=np.int32)
    n = run[:, -1] if run.shape[1] else np.zeros(ok.shape[0], dtype=np.int32)
    if not len(prices):
        return np.full(len(n), np.nan)
    lo = np.argmax(run >= np.maximum((n + 1) // 2, 1)[:, None], axis=1)
    hi = np.argmax(run >= (n // 2 + 1)[:, None], axis=1)
    return np.where(n >= MIN_NICHE, (prices[lo] + prices[hi]) / 2, np.nan)


def market_median_price(targets: pd.DataFrame, pool: pd.DataFrame, days: int = PRICE_DAYS) -> np.ndarray:
    """Median price of all paid pool games that launched in the `days` before each
    target (the fallback for small niches). NaN with fewer than MIN_NICHE."""
    pool = pool[pool["price"] > 0].sort_values("launch_ts", kind="stable")
    p_ts, prices = pool["launch_ts"].to_numpy(dtype=np.int64), pool["price"].to_numpy()
    lo_ts, hi_ts = _price_window(targets, days)
    a, b = np.searchsorted(p_ts, lo_ts, side="left"), np.searchsorted(p_ts, hi_ts, side="left")
    return np.array([np.median(prices[i:j]) if j - i >= MIN_NICHE else np.nan for i, j in zip(a, b)])


def _ts(dt: datetime) -> float:
    return dt.astimezone(timezone.utc).timestamp()


def event_features(df: pd.DataFrame, events: list[dict], tag_names: dict[int, str]) -> pd.DataFrame:
    """Steam events and releases around each launch, as 0/1 columns (EVENT_COLUMNS)."""
    ts = df["launch_ts"].to_numpy(dtype=float)
    days = np.array([d.toordinal() for d in df["launch_date"]])
    appids = df["appid"].to_numpy()
    out = {c: np.zeros(len(df), dtype=bool) for c in EVENT_COLUMNS}
    top_names = top_tag_names(df, tag_names)
    fest_ends = []
    for e in events:
        start, end = (_ts(x) for x in event_data.window(e))
        inside = (ts >= start) & (ts < end)
        kind = e["type"]
        if kind == "seasonal_sale":
            out["sale"] |= inside
            out["pre_sale"] |= (ts >= start - PRE_SALE_DAYS * DAY) & (ts < start)
        elif kind == "next_fest":
            out["next_fest"] |= inside
            fest_ends.append((start, end))
        elif kind == "themed_fest" and e.get("tags"):
            fest = set(e["tags"])
            out["themed_fest"] |= inside & np.array([bool(fest & names) for names in top_names])
        elif kind == "regional_holiday":
            col = next((c for name, c in HOLIDAYS.items() if e["name"].startswith(name)), None)
            if col:
                out[col] |= inside
        elif kind == "major_release" and not e.get("surprise") and e.get("release_kind") != "expansion":
            near = (np.abs(days - e["start"].toordinal()) <= NEAR_DAYS) & (appids != e.get("steam_appid", -1))
            if e.get("on_steam_at_launch") and not e.get("free_to_play"):
                out["big_competitor"] |= near
            else:
                out["attention_release"] |= near
    out["pre_sale"] &= ~out["sale"]
    # the last Next Fest that ended before launch, and whether the game's demo was out by its end
    fest_ends.sort(key=lambda w: w[1])
    ends = np.array([e for _, e in fest_ends])
    if len(ends):
        last = np.searchsorted(ends, ts, side="right") - 1
        demo_ts = df["demo_ts"].to_numpy(dtype=float)
        fest_end = np.where(last >= 0, ends[np.clip(last, 0, None)], -np.inf)
        out["demo_last_fest"] = (last >= 0) & (demo_ts < fest_end) & (demo_ts < ts)
    return pd.DataFrame({c: v.astype(int) for c, v in out.items()}, index=df.index)


WINDOW_KINDS = {"sale": "seasonal_sale", "next_fest": "next_fest", "themed_fest": "themed_fest",
                **{c: "regional_holiday" for c in HOLIDAYS.values()}}


def event_windows(events: list[dict], column: str) -> list[dict]:
    """The windows behind one window indicator of `event_features` (a key of
    WINDOW_KINDS), as {"name", "start", "end" (UTC seconds), "tags" (a set, or None
    for any game)}, in time order."""
    kind = WINDOW_KINDS[column]
    out = []
    for e in events:
        if e["type"] != kind or (kind == "themed_fest" and not e.get("tags")):
            continue
        holiday = next((c for n, c in HOLIDAYS.items() if e["name"].startswith(n)), None)
        if kind == "regional_holiday" and holiday != column:
            continue
        start, end = (_ts(x) for x in event_data.window(e))
        out.append({"name": e["name"], "start": start, "end": end,
                    "tags": set(e["tags"]) if kind == "themed_fest" else None})
    return sorted(out, key=lambda w: w["start"])


def window_indicator(ts: np.ndarray, windows: list[dict], top_names: list[set] | None = None) -> np.ndarray:
    """1 where the launch time falls in one of the windows (and, for a window with
    tags, one of the game's top tags is among them)."""
    out = np.zeros(len(ts), dtype=bool)
    for w in windows:
        inside = np.flatnonzero((ts >= w["start"]) & (ts < w["end"]))
        if w["tags"] is not None:
            inside = inside[np.array([bool(w["tags"] & top_names[i]) for i in inside], dtype=bool)]
        out[inside] = True
    return out


def top_tag_names(df: pd.DataFrame, tag_names: dict[int, str]) -> list[set]:
    return [{tag_names.get(t) for t, _ in pairs[:TOP]} for pairs in df["tags"]]


def publisher_reach(df: pd.DataFrame) -> pd.Series:
    """Each game's publishers' earlier launches in the data (the most of any of its
    publishers), counting any launch type with an earlier launch time. The data
    starts 2022-01-01, so for 2022 launches this undercounts (REACH_FULL_FROM)."""
    ts, pubs = df["launch_ts"].to_numpy(), list(df["publishers"])
    order = np.argsort(ts, kind="stable")
    seen: Counter = Counter()
    reach = np.zeros(len(df), dtype=np.int64)
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and ts[order[j]] == ts[order[i]]:
            j += 1
        for k in order[i:j]:
            reach[k] = max((seen[p] for p in pubs[k]), default=0)
        for k in order[i:j]:
            seen.update(set(pubs[k]))
        i = j
    return pd.Series(reach, index=df.index)


def load_followers(gp_dir: Path | None) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Follower series per game from gp/followers/*.csv.gz: (UTC seconds, followers),
    sorted by time. A point fetched more than once keeps its newest fetch."""
    if gp_dir is None:
        return {}
    files = sorted((Path(gp_dir) / "followers").glob("*.csv.gz"))
    if not files:
        return {}
    f = pd.concat([pd.read_csv(p, dtype={"followers": "Int64"}) for p in files], ignore_index=True)
    f = f.dropna(subset=["followers"]).sort_values("fetched_at")
    f = f.drop_duplicates(["appid", "observed_at"], keep="last")
    observed = pd.to_datetime(f["observed_at"], utc=True, format="ISO8601")
    f["t"] = (observed - pd.Timestamp(0, tz="UTC")) / pd.Timedelta(seconds=1)  # resolution differs by pandas version
    f = f.sort_values(["appid", "t"])
    return {int(a): (g["t"].to_numpy(), g["followers"].to_numpy(dtype=float)) for a, g in f.groupby("appid")}


def followers_at(series: tuple[np.ndarray, np.ndarray] | None, at: float) -> float | None:
    """Followers at time `at` (UTC seconds): linear between the observations around it;
    the nearest one if it is on one side only and within ONE_SIDED_DAYS; else None."""
    if series is None or not len(series[0]):
        return None
    t, f = series
    i = int(np.searchsorted(t, at))
    if i < len(t) and t[i] == at:
        return float(f[i])
    if 0 < i < len(t):
        return float(f[i - 1] + (f[i] - f[i - 1]) * (at - t[i - 1]) / (t[i] - t[i - 1]))
    j = 0 if i == 0 else len(t) - 1
    return float(f[j]) if abs(t[j] - at) <= ONE_SIDED_DAYS * DAY else None


def prelaunch_followers(df: pd.DataFrame, series: dict, days: int = FOLLOWER_DAYS) -> pd.Series:
    """log(1 + followers) `days` before launch, NaN where unknown."""
    values = [followers_at(series.get(a), ts - days * DAY) for a, ts in zip(df["appid"], df["launch_ts"])]
    return pd.Series([math.log1p(v) if v is not None else math.nan for v in values], index=df.index)


def placebo_ok(df: pd.DataFrame, data_end: date, offset_weeks: int) -> pd.Series:
    """True where the week `offset_weeks` after launch ended before `data_end` (complete in the data)."""
    return pd.Series([w + timedelta(weeks=offset_weeks, days=6) < data_end for w in df["week"]], index=df.index)


def pool_of(df: pd.DataFrame, free: bool) -> pd.DataFrame:
    """Launches that count as competition for a group: full or Early Access, same group."""
    return df[df["launch_type"].isin(PANEL_TYPES) & (df["free"] == free)]
