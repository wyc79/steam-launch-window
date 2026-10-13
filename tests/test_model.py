import gzip
import json
import random
from datetime import date, datetime, timedelta, timezone

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("statsmodels")
yaml = pytest.importorskip("yaml")

from analysis import model as M  # noqa: E402
from pipeline import storage  # noqa: E402
from pipeline.collect_history import FIELDS  # noqa: E402

TAGS = {19: "Action", 492: "Indie", 1716: "Roguelike", 1664: "Puzzle", 599: "Simulation", 113: "Free to Play"}


def test_hour_bands():
    assert [M.hour_band(h) for h in (0, 5, 6, 9, 10, 12, 13, 17, 18, 23)] == \
        ["0_5", "0_5", "6_9", "6_9", "10_12", "10_12", "13_17", "13_17", "18_23", "18_23"]


def test_fit_nb_recovers_a_rate_ratio():
    pd = pytest.importorskip("pandas")
    rng = np.random.default_rng(1)
    n = 3000
    x = rng.integers(0, 2, n)
    mu = np.exp(1.0 + np.log(0.5) * x)
    y = rng.negative_binomial(1.0, 1 / (1 + mu))
    s = pd.DataFrame({"y": y, "x": x, "week": rng.integers(0, 50, n)})
    res = M.fit_nb(s, ["x"])
    assert not res.preliminary and res.n_weeks == 50
    assert np.exp(res.params["x"]) == pytest.approx(0.5, abs=0.1)


def make_data(root, n=2500, seed=3, free_purchase=""):
    """Launches from 2022-09 to 2026-08 (some before REACH_FULL_FROM and some held out).
    free_purchase is the free rows' reviews_purchase ("all": recounted)."""
    rng = random.Random(seed)
    rows = []
    start = date(2022, 9, 1)
    for i in range(n):
        day = start + timedelta(days=rng.randrange(0, 1450))
        ts = int(datetime(day.year, day.month, day.day, rng.randrange(24), tzinfo=timezone.utc).timestamp())
        tags = rng.sample([19, 492, 1716, 1664, 599], 3)
        free = rng.random() < 0.35
        r = dict.fromkeys(FIELDS, "")
        r.update(appid=1000 + i, name=f"g{i}", launch_date=day.isoformat(), launch_ts=ts,
                 launch_type=rng.choice(["full", "full", "early_access"]), price_cents=0 if free else rng.choice(
                     [199, 499, 999, 1999, 2999]), is_free=int(free),
                 tags="|".join(f"{t}:{100 - 10 * k}" for k, t in enumerate(tags)),
                 languages=rng.choice(["english", "english|schinese", "english|japanese|german"]),
                 audio_languages=rng.choice(["", "english"]), publishers=f"P{rng.randrange(200)}",
                 franchises=rng.choice(["", "", "", "F"]), demo_before_launch=rng.choice(["", "1"]),
                 reviews_30d=int(np.random.default_rng(i).negative_binomial(0.5, 0.05)), reviews_30d_source="api",
                 reviews_purchase=free_purchase if free else "")
        rows.append(r)
    rows.sort(key=lambda r: int(r["appid"]))
    storage.write_csv(root / "history" / "games.csv", rows, FIELDS)
    storage.write_csv(root / "tags.csv", [{"tagid": t, "name": n} for t, n in TAGS.items()], ["tagid", "name"])
    events = [
        {"name": "Steam Summer Sale 2024", "type": "seasonal_sale", "start": date(2024, 6, 27),
         "end": date(2024, 7, 11)},
        {"name": "Steam Next Fest October 2024", "type": "next_fest", "start": date(2024, 10, 14),
         "end": date(2024, 10, 21)},
        {"name": "Steam Rogue Fest 2025", "type": "themed_fest", "start": date(2025, 5, 5), "end": date(2025, 5, 12),
         "tags": ["Roguelike"]},
        {"name": "Big Game", "type": "major_release", "start": date(2025, 3, 3), "end": date(2025, 3, 3),
         "on_steam_at_launch": True, "release_kind": "full", "steam_appid": 5},
        {"name": "China National Day holiday 2025", "type": "regional_holiday", "start": date(2025, 10, 1),
         "end": date(2025, 10, 8), "region": "CN"},
    ]
    (root / "events.yaml").write_text(yaml.safe_dump({"events": events}), encoding="ascii")
    # follower series for the first 700 games: a straight line around launch
    lines = ["appid,followers,observed_at,fetched_at"]
    for r in rows[:700]:
        launch = int(r["launch_ts"])
        for d in (-30, -10, -3, 2):
            t = datetime.fromtimestamp(launch + d * 86400, timezone.utc).isoformat()
            lines.append(f"{r['appid']},{100 + 3 * (d + 30) + int(r['appid']) % 50},{t},2026-10-12T00:00:00+00:00")
    (root / "gp" / "followers").mkdir(parents=True)
    with gzip.open(root / "gp" / "followers" / "2026-10-12.csv.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    make_data(root, free_purchase="all")
    return root


@pytest.fixture(scope="module")
def frames(data_dir):
    return M.build_frames(data_dir, data_dir / "events.yaml", data_dir / "gp")


def test_model_cli_writes_model_json(data_dir, frames, tmp_path, capsys):
    out = tmp_path / "site"
    assert M.main(["--data-dir", str(data_dir), "--gp-dir", str(data_dir / "gp"), "--events",
                   str(data_dir / "events.yaml"), "--out", str(out), "--permutations", "20"]) == 0
    result = json.loads((out / "model.json").read_text(encoding="utf-8"))
    n = result["sample"]
    assert n["paid_without_earlier_prices"] > 0   # the first days of the data: left out, no niche price
    assert n["kept"] == n["paid"] + n["free"] + n["paid_without_price"] + n["paid_without_earlier_prices"]
    assert result["followers"]["games_with_series"] == 700
    for group in ("paid", "free"):
        g = result[group]
        keys = {e["key"] for e in g["reviews"]["effects"]}
        assert g["competition_measure"] in keys and {"sale", "early_access", "demo"} <= keys
        assert g["reviews"]["n"] == result["sample"][group]
        assert {"top5", "top20", "small_games", "placebo"} <= set(g["checks"])
        placebo = g["checks"]["placebo"]
        assert placebo["measure"] == M.PLACEBO[g["competition_measure"]]  # the same rule as the main measure
        assert {e["key"] for e in placebo["placebo"]["effects"]} == {placebo["measure"]}
        assert {e["key"] for e in placebo["together"]["effects"]} == {g["competition_measure"], placebo["measure"]}
        assert g["chance_test"]["draws"] == 20
        sale = next(e for e in g["reviews"]["effects"] if e["key"] == "sale")
        assert 0 < sale["chance_p"] <= 1 and sale["windows"] == 1
        assert "count_given_some" in g["hurdle"] and "converged" in g["hurdle"]["count_given_some"]
        assert {"model", "baseline"} <= set(g["held_out"])
        assert g["followers"]["games"] > 0
    assert "revenue" in result["paid"] and "log_price" in {e["key"] for e in result["paid"]["reviews"]["effects"]}
    assert "log_price" not in {e["key"] for e in result["free"]["reviews"]["effects"]}
    assert "with_followers" in result["paid"]["followers"]
    # every free row is recounted in this data: the free model is fitted and read
    free = result["free"]
    assert (free["status"], free["recounted_share"], free["recounted"]) == ("ok", 1.0, True)
    assert M.FREE_CAVEAT not in free["caveats"] and "recounted_share" not in result["paid"]
    assert "== paid" in capsys.readouterr().out
    # small games: launched from REACH_FULL_FROM only (the data starts before it)
    s = frames[0]["paid"]
    small = (s["reach"] <= M.SMALL_REACH) & (s["franchise"] == 0) & (s["price"] < M.SMALL_PRICE)
    late = s["launch_date"] >= M.F.REACH_FULL_FROM
    assert result["paid"]["checks"]["small_games"]["n"] == int((small & late).sum()) < int(small.sum())


def test_tier_placebo_counts_the_same_tier_8_weeks_later(data_dir, frames):
    s = frames[0]["paid"]
    pool = M.F.pool_of(M.F.load_history(data_dir / "history" / "games.csv"), False)
    expected = M.F.similar_counts(s, pool, offset_weeks=M.PLACEBO_WEEKS, same_tier=True)
    assert list(s["comp_tier_placebo"]) == list(expected)
    assert (s["comp_tier_placebo"] < s["comp_placebo"]).any()      # the tier rule bites in this data
    assert (s["comp_tier_placebo"] <= s["comp_placebo"]).all()


def test_today_caps_the_data(data_dir, frames):
    today = date(2025, 12, 31)
    capped, info = M.build_frames(data_dir, data_dir / "events.yaml", data_dir / "gp", today=today)
    assert info["sample"]["sample_end"] == "2025-11-30"
    s, full = capped["paid"], frames[0]["paid"].set_index("appid")
    history = M.F.load_history(data_dir / "history" / "games.csv")
    data_end = max(d for d in history["launch_date"] if d <= today)
    # the placebo week must end before the capped data end, not the real one
    assert list(s["placebo_ok"]) == [w + timedelta(weeks=M.PLACEBO_WEEKS, days=6) < data_end for w in s["week"]]
    assert not s["placebo_ok"].all() and full.loc[s.loc[~s["placebo_ok"], "appid"], "placebo_ok"].any()
    # launches after `today` are not in the pool: a placebo week after it counts nothing
    after = [w + timedelta(weeks=M.PLACEBO_WEEKS) > today for w in s["week"]]
    assert (s.loc[after, "comp_placebo"] == 0).all()
    assert (full.loc[s.loc[after, "appid"], "comp_placebo"] > 0).any()


def test_held_out_genres_come_from_the_fitting_years(monkeypatch):
    # tag 19 leads before HELD_OUT_FROM; tag 492 leads overall because of the held-out year
    rows = [{"launch_date": date(2025, 6, 1), "tags": [(19, 10)]}] * 30 + \
           [{"launch_date": date(2025, 6, 1), "tags": [(492, 10)]}] * 10 + \
           [{"launch_date": date(2026, 3, 1), "tags": [(492, 10)]}] * 40
    s = pd.DataFrame(rows)
    seen = {}

    class Stop(Exception):
        pass

    def spy(frame, cols):
        seen.update(cols)
        raise Stop

    monkeypatch.setattr(M, "GENRES", 1)
    monkeypatch.setattr(M, "held_out", spy)
    with pytest.raises(Stop):
        M.run_group(s, free=True)
    assert "tag_19" in seen["model"] and "tag_492" not in seen["model"]
    assert "tag_19" in seen["baseline"] and "tag_492" not in seen["baseline"]


# --- pieces -----------------------------------------------------------------

class FakeResult:
    def __init__(self, params, se):
        self.params = pd.Series(params)
        self.bse = pd.Series(se)
        self.pvalues = pd.Series(0.01, index=self.params.index)

    def conf_int(self):
        return pd.DataFrame({0: self.params - 2 * self.bse, 1: self.params + 2 * self.bse})


pd = pytest.importorskip("pandas")


def test_effects_scale_doublings_and_per_10():
    res = FakeResult({"log_price": 0.5, "comp_tier": -0.01, "sale": -0.4},
                     {"log_price": 0.1, "comp_tier": 0.001, "sale": 0.1})
    s = pd.DataFrame({"log_price": [1.0, 2.0], "comp_tier": [3, 5], "sale": [0, 1]})
    e = {r["key"]: r for r in M.effects(res, s)}
    assert e["log_price"]["rate_ratio"] == pytest.approx(np.exp(0.5 * np.log(2)), rel=1e-3)   # per doubling
    assert e["log_price"]["low"] == pytest.approx(np.exp(0.3 * np.log(2)), rel=1e-3)
    assert e["sale"]["rate_ratio"] == pytest.approx(np.exp(-0.4), rel=1e-3) and e["sale"]["games_with"] == 1
    assert "per_10" not in e["sale"]
    assert e["comp_tier"]["rate_ratio"] == pytest.approx(np.exp(-0.01), rel=1e-3)
    assert e["comp_tier"]["per_10"]["ratio"] == pytest.approx(np.exp(-0.1), rel=1e-3)
    assert e["comp_tier"]["per_10"]["high"] == pytest.approx(np.exp(-0.08), rel=1e-3)
    # with the Simplified Chinese extra in the model, the holiday's own effect is for games without it
    res = FakeResult({"cn_spring": -0.4, "cn_spring_x_schinese": 0.1}, {"cn_spring": 0.1, "cn_spring_x_schinese": 0.1})
    s = pd.DataFrame({"cn_spring": [1, 1, 1, 0], "cn_spring_x_schinese": [1, 0, 0, 0]})
    e = {r["key"]: r for r in M.effects(res, s)}
    assert e["cn_spring"]["games_with"] == 2 and e["cn_spring_x_schinese"]["games_with"] == 1


def truncated_data(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    d = rng.integers(0, 2, n)
    mu = np.exp(1 + 0.5 * x + np.log(0.6) * d)
    y = rng.negative_binomial(1 / 0.8, 1 / (1 + 0.8 * mu))
    pos = y > 0
    X = pd.DataFrame({"const": 1.0, "x": x, "d": d.astype(float)})[pos]
    return y[pos].astype(float), X, rng.integers(0, 60, n)[pos]


def test_truncated_nb_matches_statsmodels_and_checks_convergence(monkeypatch):
    import statsmodels.api as sm
    from statsmodels.discrete.truncated_model import TruncatedLFNegativeBinomialP

    y, X, groups = truncated_data()
    start = sm.NegativeBinomial(y, X).fit(disp=0).params
    res, method, failure = M.fit_truncated_nb(y, X, groups, start)
    assert failure is None and method.startswith("bfgs")
    ref = TruncatedLFNegativeBinomialP(y, X, truncation=0, p=2).fit(
        start_params=start.to_numpy(), method="newton", disp=0, cov_type="cluster", cov_kwds={"groups": groups})
    assert np.allclose(res.params.to_numpy(), ref.params.to_numpy(), atol=1e-4)
    assert np.allclose(res.bse.to_numpy(), ref.bse.to_numpy(), rtol=1e-3)
    assert np.exp(res.params["d"]) == pytest.approx(0.6, abs=0.08)
    monkeypatch.setattr(M, "TRUNC_TOL", 0.0)            # a gradient can never be this small: reported as failed
    res, method, failure = M.fit_truncated_nb(y, X, groups, start)
    assert res is None and failure.startswith("did not converge")
    monkeypatch.setattr(M, "TRUNC_TOL", 1e-6)
    monkeypatch.setattr(M, "TRUNC_MAX_ALPHA", 0.1)      # alpha past the limit: no finite maximum
    assert M.fit_truncated_nb(y, X, groups, start)[2].startswith("no finite maximum")


def test_hurdle_leaves_out_a_failed_count_part(monkeypatch):
    rng = np.random.default_rng(2)
    n = 1500
    x = rng.integers(0, 2, n)
    s = pd.DataFrame({"x": x, "week": rng.integers(0, 40, n),
                      "y": rng.negative_binomial(1.0, 1 / (1 + np.exp(1.0 - 0.5 * x)))})
    monkeypatch.setitem(M.LABELS, "x", "x")
    h = M.fit_hurdle(s, ["x"])
    assert h["count_given_some"]["converged"] and h["count_given_some"]["effects"]
    monkeypatch.setattr(M, "fit_truncated_nb", lambda *a: (None, None, "did not converge (test)"))
    h = M.fit_hurdle(s, ["x"])
    part = h["count_given_some"]
    assert part["converged"] is False and part["effects"] == [] and "did not converge" in part["status"]
    assert h["count_given_some_plain_nb"]["effects"]
    caveats = M.group_caveats({"status": "ok", "hurdle": h, "checks": {"placebo": PLACEBO_NOISE}}, free=False)
    assert any("no stable fit" in c and "not corrected for the missing zeros" in c for c in caveats)
    assert not any("did not converge" in c for c in caveats)     # the technical reason stays in "failure"


def test_free_model_is_read_once_95_percent_are_recounted():
    pd = pytest.importorskip("pandas")

    def frame(n=100, zeros=10):
        return pd.DataFrame({"y": [0] * zeros + [5] * (n - zeros)})

    def caveats(g, free=True):
        return M.group_caveats({**g, "hurdle": {"count_given_some": {}}, "checks": {"placebo": PLACEBO_NOISE}}, free)

    before = M.group_status(frame(), True, (100, 94))
    assert (before["status"], before["recounted_share"], before["recounted"]) == ("unreliable", 0.94, False)
    assert before["recount"] == {"launches": 100, "recounted": 94}
    assert caveats(before) == [M.FREE_CAVEAT]
    after = M.group_status(frame(), True, (100, 95))
    assert (after["status"], after["recounted_share"], after["recounted"]) == ("ok", 0.95, True)
    assert caveats(after) == []
    # no free launches at all: not recounted
    assert M.group_status(frame(), True)["status"] == "unreliable"
    # recounted, but still mostly zeros: unreliable, with its own caveat
    zeros = M.group_status(frame(zeros=85), True, (100, 100))
    assert zeros["status"] == "unreliable" and caveats(zeros) == [
        "85% of these launches have no reviews in their first 30 days, too many for the model to be read."]
    # paid games do not depend on the recount
    assert M.group_status(frame(), False) == {"status": "ok", "zero_share": 0.1}


def test_free_model_is_not_ready_while_a_recount_runs(tmp_path):
    # the recount has started: every free row is "all", but only every 4th has its count back
    make_data(tmp_path, n=800)
    rows = storage.read_csv(tmp_path / "history" / "games.csv")
    free = [r for r in rows if r["is_free"] == "1"]
    for i, r in enumerate(free):
        r["reviews_purchase"] = "all"
        if i % 4:
            r.update(reviews_30d="", reviews_30d_source="")
    storage.write_csv(tmp_path / "history" / "games.csv", rows, FIELDS)
    frames, info = M.build_frames(tmp_path, tmp_path / "events.yaml", tmp_path / "gp")
    s = frames["free"]
    assert (s["purchase"] == "all").all()          # the fitted rows alone would read 100% recounted
    launches, done = info["free_recount"]
    assert done == len(s) and launches > 3 * done
    status = M.group_status(s, True, info["free_recount"])
    assert status["status"] == "unreliable" and not status["recounted"] and status["recounted_share"] < 0.3


def test_partial_recount_skips_the_free_fit_and_still_writes_paid(tmp_path, capsys):
    # the recount has just started: 95% of free rows are marked "all" with their count blanked,
    # which leaves a few dozen free rows, nearly all zeros (fitting them crashed the run)
    make_data(tmp_path)
    rows = storage.read_csv(tmp_path / "history" / "games.csv")
    for i, r in enumerate(r for r in rows if r["is_free"] == "1"):
        r["reviews_purchase"] = "all"
        if i % 20:
            r.update(reviews_30d="", reviews_30d_source="")
    storage.write_csv(tmp_path / "history" / "games.csv", rows, FIELDS)
    out = tmp_path / "site"
    assert M.main(["--data-dir", str(tmp_path), "--gp-dir", str(tmp_path / "gp"), "--events",
                   str(tmp_path / "events.yaml"), "--out", str(out), "--permutations", "5"]) == 0
    result = json.loads((out / "model.json").read_text(encoding="utf-8"))
    assert result["paid"]["status"] == "ok" and result["paid"]["reviews"]["effects"]
    free = result["free"]
    assert (free["status"], free["recounted"], free["caveats"]) == ("unreliable", False, [M.FREE_CAVEAT])
    assert free["recount"]["recounted"] < 0.1 * free["recount"]["launches"] and "reviews" not in free
    printed = capsys.readouterr().out
    assert f"== free: not fitted, status unreliable (recounted {free['recount']['recounted']} of " in printed


@pytest.mark.parametrize("broken", ["paid", "free"])
def test_a_failed_group_still_writes_the_other(data_dir, tmp_path, monkeypatch, broken):
    real = M.run_group

    def run_group(s, free, *a, **k):
        if free == (broken == "free"):
            raise OverflowError("math range error")
        return real(s, free, *a, **k)

    monkeypatch.setattr(M, "run_group", run_group)
    out = tmp_path / "site"
    code = M.main(["--data-dir", str(data_dir), "--gp-dir", str(data_dir / "gp"), "--events",
                   str(data_dir / "events.yaml"), "--out", str(out), "--permutations", "2"])
    assert code == (1 if broken == "paid" else 0)   # only a failed paid model fails the run
    result = json.loads((out / "model.json").read_text(encoding="utf-8"))
    other = "free" if broken == "paid" else "paid"
    assert result[broken]["status"] == "failed" and result[broken]["error"] == "OverflowError: math range error"
    assert result[other]["status"] == "ok" and result[other]["reviews"]["effects"]


def test_history_reads_reviews_purchase(tmp_path):
    make_data(tmp_path, n=3)
    rows = storage.read_csv(tmp_path / "history" / "games.csv")
    rows[0]["reviews_purchase"] = "all"
    storage.write_csv(tmp_path / "history" / "games.csv", rows, FIELDS)
    assert list(M.F.load_history(tmp_path / "history" / "games.csv")["purchase"]) == ["all", "", ""]
    old = [f for f in FIELDS if f != "reviews_purchase"]   # a file from before PR #20
    storage.write_csv(tmp_path / "history" / "games.csv", rows, old)
    assert list(M.F.load_history(tmp_path / "history" / "games.csv")["purchase"]) == ["", "", ""]


def effect(key, ratio, low, high, p):
    return {"key": key, "rate_ratio": ratio, "low": low, "high": high, "p": p}


def placebo(alone, real, together_real, together_placebo, n=65380):
    key, pkey = "comp_tier", "comp_tier_placebo"
    return {"measure": pkey, "placebo": {"n": n, "effects": [effect(pkey, *alone)]},
            "real_same_sample": {"n": n, "effects": [effect(key, *real)]},
            "together": {"n": n, "effects": [effect(key, *together_real), effect(pkey, *together_placebo)]}}


PLACEBO_NOISE = placebo((0.999, 0.99, 1.008, 0.8), (0.99, 0.98, 0.995, 0.001), (0.99, 0.98, 0.995, 0.001),
                        (1.0, 0.99, 1.01, 0.9))


def test_placebo_caveat_is_built_from_the_numbers():
    assert M.placebo_caveat(PLACEBO_NOISE) is None      # placebo within noise: no caveat
    text = M.placebo_caveat(placebo((0.991, 0.988, 0.994, 1e-6), (0.991, 0.988, 0.994, 1e-6),
                                    (0.994, 0.988, 1.000, 0.05), (0.996, 0.992, 1.0, 0.04)))
    assert "0.9% fewer" in text and "65,380 games" in text and "about as large" in text
    assert "0.994 (0.988 to 1.000, at the edge of noise)" in text and "small at most" in text
    other_way = M.placebo_caveat(placebo((1.02, 1.01, 1.03, 1e-4), (0.98, 0.97, 0.99, 1e-4),
                                         (0.97, 0.96, 0.98, 1e-5), (1.03, 1.02, 1.04, 1e-5)))
    assert "2.0% more" in other_way and "other way" in other_way and "small at most" not in other_way
    assert "0.970 (0.960 to 0.980, clear)" in other_way
    smaller = M.placebo_caveat(placebo((0.995, 0.99, 0.999, 0.01), (0.98, 0.97, 0.99, 1e-4),
                                       (0.982, 0.97, 0.99, 1e-4), (0.998, 0.99, 1.0, 0.5)))
    assert "smaller than the real effect" in smaller
    # the free games' numbers: the real week within noise, the placebo not
    noise = M.placebo_caveat(placebo((0.969, 0.939, 0.9996, 0.04), (0.992, 0.958, 1.028, 0.6),
                                     (1.009, 0.971, 1.049, 0.6), (0.965, 0.931, 0.999, 0.04), n=11928))
    assert "nothing clear" in noise and "0.992, 0.958 to 1.028" in noise
    assert "explains a lot" not in noise and "smaller than" not in noise


def holiday_group(spring_x=(1.13, 0.76, 1.68, 0.5), hurdle_x=(0.712, 0.548, 0.926, 0.01)):
    return {"reviews": {"effects": [
                effect("cn_spring", 0.63, 0.46, 0.86, 0.004), effect("cn_spring_x_schinese", *spring_x),
                effect("cn_national", 0.44, 0.29, 0.67, 0.001),
                effect("cn_national_x_schinese", 1.09, 0.64, 1.84, 0.7)]},
            "chance_test": {"cn_spring": {"ratio_alone": 0.70, "p_value": 0.085, "windows": 2}},
            "hurdle": {"any_reviews": {"effects": [
                {**effect("cn_spring_x_schinese", *hurdle_x[:3], hurdle_x[3]), "odds_ratio": hurdle_x[0]},
                {**effect("cn_national_x_schinese", 0.86, 0.46, 1.59, 0.6), "odds_ratio": 0.86}]}}}


HOLIDAY_WINDOWS = {"cn_spring": [{"name": "a", "overlaps": ["sale"]}, {"name": "b", "overlaps": []}],
                   "cn_national": [{"name": "c", "overlaps": ["fest"]}],
                   "with_schinese": {"cn_spring": effect("cn_spring_schinese", 0.71, 0.50, 1.01, 0.06),
                                     "cn_national": effect("cn_national_schinese", 0.48, 0.30, 0.77, 0.002)}}


def test_holiday_note_from_the_numbers():
    note = M.holiday_note(holiday_group(), HOLIDAY_WINDOWS)
    assert "games without Simplified Chinese 37% fewer reviews (0.63 (0.46 to 0.86))" in note
    assert "games with it no clear difference (0.71 (0.50 to 1.01))" in note     # the combined effect
    assert "games with it 52% fewer reviews (0.48 (0.30 to 0.77))" in note
    assert "the chance test (all games pooled) gives 0.70 with p = 0.085" in note
    assert "no clear difference, but the intervals are wide" in note and "not about Chinese players" not in note
    assert "less likely to get any review" in note and "0.71 (0.55 to 0.93)" in note   # the hurdle extra
    assert "National Day were" not in note                       # its hurdle extra is within noise
    assert "2 of the 3 holiday windows" in note and "2 Spring Festival and 1 National Day" in note
    clear = M.holiday_note(holiday_group(spring_x=(1.6, 1.1, 2.3, 0.01), hurdle_x=(0.9, 0.7, 1.1, 0.4)),
                           HOLIDAY_WINDOWS)
    assert "wide" not in clear and "any review" not in clear


def test_combined_effect_uses_the_covariance():
    class Res:
        params = pd.Series({"a": -0.5, "b": 0.1})
        def cov_params(self):
            return pd.DataFrame([[0.04, -0.01], [-0.01, 0.09]], index=["a", "b"], columns=["a", "b"])

    monkey = pd.DataFrame({"b": [1, 0, 1]})
    c = M.combined_effect(Res(), monkey, "a", "b")
    se = np.sqrt(0.04 + 0.09 - 0.02)
    assert c["rate_ratio"] == pytest.approx(np.exp(-0.4), rel=1e-3) and c["games_with"] == 2
    assert c["low"] == pytest.approx(np.exp(-0.4 - 1.959964 * se), rel=1e-3)
    assert c["high"] == pytest.approx(np.exp(-0.4 + 1.959964 * se), rel=1e-3)
    assert M.combined_effect(Res(), monkey, "a", "c") is None


def test_chance_test_pieces():
    week = 7 * 86400
    windows = [{"name": "a", "start": 100 * week, "end": 101 * week, "tags": None},
               {"name": "b", "start": 150 * week, "end": 152 * week, "tags": None}]
    rng = np.random.default_rng(0)
    for _ in range(50):
        moved = M.move_windows(windows, rng, 90 * week, 200 * week)
        assert len(moved) == 2
        for m, w in zip(moved, windows):
            assert round((m["start"] - w["start"]) / week * 168) % 168 in (0, 1, 167)   # whole weeks, give or take DST
            assert 90 * week <= m["start"] and m["end"] <= 200 * week
        assert not any(M._clash(a, b) for a in moved for b in windows)
        assert not M._clash(*moved)
    assert M.move_windows(windows, rng, 99 * week, 102 * week) is None       # no room for the second window
    tagged = {"name": "t", "start": 0, "end": 10, "tags": {"Roguelike"}}
    assert not M._clash(tagged, {**tagged, "tags": {"Puzzle"}}) and M._clash(tagged, {**tagged, "name": "u"})
    # a fake window never sits on a real one, even one for other tags
    fests = [{"name": "r", "start": 100 * week, "end": 101 * week, "tags": {"Roguelike"}},
             {"name": "p", "start": 103 * week, "end": 104 * week, "tags": {"Puzzle"}}]
    for _ in range(50):
        moved = M.move_windows(fests, rng, 99 * week, 106 * week)
        assert moved is not None and not any(M._overlap(m, f) for m in moved for f in fests)
    # the same Pacific clock time across daylight saving: 10:00 PST in January to 10:00 PDT in July
    pacific = M.event_data.PACIFIC
    jan = datetime(2025, 1, 6, 10, tzinfo=pacific)
    moved = datetime.fromtimestamp(M._shift(jan.timestamp(), 26), pacific)
    assert (moved.date(), moved.hour, moved.minute) == (date(2025, 7, 7), 10, 0)
    # one coefficient with the rest held fixed recovers a known rate ratio
    n = 20000
    eta = rng.normal(1.0, 0.5, n)
    d = rng.random(n) < 0.2
    mu = np.exp(eta + np.log(0.7) * d)
    y = rng.negative_binomial(1.0, 1 / (1 + mu)).astype(float)
    assert np.exp(M.one_coefficient(y, eta, 1.0, d)) == pytest.approx(0.7, abs=0.05)


def test_chance_test_draws_do_not_depend_on_the_other_indicators(frames, monkeypatch):
    fr, info = frames
    s = fr["paid"]
    args = (s, False, "competition", info["events"], info["tag_names"], 8)
    monkeypatch.setattr(M, "PERMUTED", ("sale", "next_fest"))
    both = M.chance_tests(*args)
    monkeypatch.setattr(M, "PERMUTED", ("next_fest",))
    alone = M.chance_tests(*args)
    assert both["next_fest"]["draws_used"] > 0 and both["next_fest"] == alone["next_fest"]
