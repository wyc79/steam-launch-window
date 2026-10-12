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
                   str(tmp_path / "events.yaml"), "--out", str(out)]) == 0
    result = json.loads((out / "model.json").read_text(encoding="utf-8"))
    assert result["sample"]["kept"] == result["sample"]["paid"] + result["sample"]["free"]
    assert result["followers"]["games_with_series"] == 400
    for group in ("paid", "free"):
        g = result[group]
        keys = {e["key"] for e in g["reviews"]["effects"]}
        assert {"competition", "sale", "early_access", "demo"} <= keys or g["competition_measure"] in keys
        assert g["reviews"]["n"] == result["sample"][group]
        assert {"top5", "top20", "small_games", "placebo"} <= set(g["checks"])
        assert {"model", "baseline"} <= set(g["held_out"])
        assert g["followers"]["games"] > 0
    assert "revenue" in result["paid"] and "log_price" in {e["key"] for e in result["paid"]["reviews"]["effects"]}
    assert "log_price" not in {e["key"] for e in result["free"]["reviews"]["effects"]}
    assert "with_followers" in result["paid"]["followers"]
    assert "== paid" in capsys.readouterr().out
