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


def make_data(root, n=2500, seed=3):
    rng = random.Random(seed)
    rows = []
    start = date(2024, 1, 1)
    for i in range(n):
        day = start + timedelta(days=rng.randrange(0, 960))
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
                 reviews_30d=int(np.random.default_rng(i).negative_binomial(0.5, 0.05)), reviews_30d_source="api")
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
    # follower series for the first 400 games: a straight line from 2023 on
    lines = ["appid,followers,observed_at,fetched_at"]
    for r in rows[:400]:
        launch = int(r["launch_ts"])
        for d in (-30, -10, -3, 2):
            t = datetime.fromtimestamp(launch + d * 86400, timezone.utc).isoformat()
            lines.append(f"{r['appid']},{100 + 3 * (d + 30) + int(r['appid']) % 50},{t},2026-10-12T00:00:00+00:00")
    (root / "gp" / "followers").mkdir(parents=True)
    with gzip.open(root / "gp" / "followers" / "2026-10-12.csv.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def test_model_cli_writes_model_json(tmp_path, capsys):
    make_data(tmp_path)
    out = tmp_path / "site"
    assert M.main(["--data-dir", str(tmp_path), "--gp-dir", str(tmp_path / "gp"), "--events",
                   str(tmp_path / "events.yaml"), "--out", str(out), "--permutations", "20"]) == 0
    result = json.loads((out / "model.json").read_text(encoding="utf-8"))
    assert result["sample"]["kept"] == result["sample"]["paid"] + result["sample"]["free"]
    assert result["followers"]["games_with_series"] == 400
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
    assert "== paid" in capsys.readouterr().out


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
    assert any("did not converge" in c for c in caveats)


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


def test_holiday_note_from_the_numbers():
    g = {"reviews": {"effects": [
        {**effect("cn_spring", 0.64, 0.46, 0.87, 0.01), "chance_p": 0.21},
        effect("cn_spring_x_schinese", 1.14, 0.76, 1.72, 0.5),
        effect("cn_national", 0.43, 0.28, 0.65, 0.001), effect("cn_national_x_schinese", 1.10, 0.65, 1.87, 0.7)]}}
    windows = {"cn_spring": [{"name": "a", "overlaps": ["sale"]}, {"name": "b", "overlaps": []}],
               "cn_national": [{"name": "c", "overlaps": ["fest"]}]}
    note = M.holiday_note(g, windows)
    assert "0.64 (0.46 to 0.87), chance test p = 0.21" in note and "not about Chinese players" in note
    assert "2 of the 3 holiday windows" in note and "2 Spring Festival and 1 National Day" in note


def test_chance_test_pieces():
    week = 7 * 86400
    windows = [{"name": "a", "start": 100 * week, "end": 101 * week, "tags": None},
               {"name": "b", "start": 150 * week, "end": 152 * week, "tags": None}]
    rng = np.random.default_rng(0)
    for _ in range(50):
        moved = M.move_windows(windows, rng, 90 * week, 200 * week)
        assert len(moved) == 2
        for m, w in zip(moved, windows):
            assert (m["start"] - w["start"]) % week == 0 and m["end"] - m["start"] == w["end"] - w["start"]
            assert 90 * week <= m["start"] and m["end"] <= 200 * week
        assert not any(M._clash(a, b) for a in moved for b in windows)
        assert not M._clash(*moved)
    assert M.move_windows(windows, rng, 99 * week, 102 * week) is None       # no room for the second window
    tagged = {"name": "t", "start": 0, "end": 10, "tags": {"Roguelike"}}
    assert not M._clash(tagged, {**tagged, "tags": {"Puzzle"}}) and M._clash(tagged, {**tagged, "name": "u"})
    # one coefficient with the rest held fixed recovers a known rate ratio
    n = 20000
    eta = rng.normal(1.0, 0.5, n)
    d = rng.random(n) < 0.2
    mu = np.exp(eta + np.log(0.7) * d)
    y = rng.negative_binomial(1.0, 1 / (1 + mu)).astype(float)
    assert np.exp(M.one_coefficient(y, eta, 1.0, d)) == pytest.approx(0.7, abs=0.05)
