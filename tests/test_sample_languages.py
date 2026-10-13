from pipeline import sample_languages as sl
from pipeline import steam, storage
from pipeline import collect_history as ch

SEP_1 = 1788246000  # 2026-09-01 00:00 Pacific


def game(appid, chinese, reviews=50, launch="2025-03-01", **kw):
    return {"appid": str(appid), "launch_date": launch, "launch_ts": str(SEP_1), "launch_type": "full",
            "is_free": "0", "tags": "492:10", "languages": "english|schinese" if chinese else "english",
            "reviews_30d": str(reviews), "reviews_30d_source": "api", **kw}


def history(tmp_path, rows):
    storage.write_csv(tmp_path / "history" / "games.csv", rows, ch.FIELDS)


def test_pick_takes_half_with_chinese_from_eligible_paid_launches_only():
    from datetime import date
    rows = ([game(i, True) for i in range(1, 11)] + [game(i, False) for i in range(11, 21)]
            + [game(30, True, reviews=3), game(31, True, is_free="1"), game(32, False, launch_type="ea_exit"),
               game(33, False, launch="2022-06-01"), game(34, False, tags="113:50")])
    picked = sl.pick(rows, 8, date(2023, 1, 1), date(2026, 9, 1), 10, seed=0)
    ids = [int(r["appid"]) for r in picked]
    assert len(ids) == 8 and sum(i <= 10 for i in ids) == 4  # half supporting Simplified Chinese
    assert not set(ids) & {30, 31, 32, 33, 34}                  # few reviews, free, ea_exit, too old, F2P tag
    assert sl.pick(rows, 8, date(2023, 1, 1), date(2026, 9, 1), 10, seed=0) == picked  # same pick on a rerun


def test_counts_every_language_resumes_and_records_missing_data(tmp_path, monkeypatch):
    history(tmp_path, [game(1, True), game(2, False)])
    calls = []

    def counts(client, appid, start, end, purchase_type=steam.PURCHASE_STEAM, language="all"):
        calls.append((int(appid), language, purchase_type))
        if int(appid) == 2 and language == "koreana":
            raise steam.Unavailable("no data")
        return {"total": 7, "positive": 5, "negative": 2}
    monkeypatch.setattr(steam, "review_counts", counts)
    args = ["--data-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--games", "2",
            "--today", "2026-10-20", "--fail-if-incomplete"]
    assert sl.main(args) == 0
    out = storage.read_csv(tmp_path / "history" / "reviews_by_language.csv")
    assert len(out) == 2 * len(sl.LANGUAGES) and len(calls) == 2 * len(sl.LANGUAGES)
    assert {c[2] for c in calls} == {steam.PURCHASE_STEAM} and calls[0][1] == "all"
    row = next(r for r in out if r["appid"] == "2" and r["language"] == "koreana")
    assert (row["reviews"], row["schinese_supported"]) == ("", "0")
    assert next(r for r in out if r["appid"] == "1")["schinese_supported"] == "1"
    calls.clear()
    assert sl.main(args) == 0 and calls == []  # a rerun has nothing left to count


def _fake(monkeypatch, gone=()):
    calls = []

    def counts(client, appid, start, end, purchase_type=steam.PURCHASE_STEAM, language="all"):
        calls.append((int(appid), language))
        if int(appid) in gone:
            raise steam.Unavailable("no data")
        return {"total": 7, "positive": 5, "negative": 2}
    monkeypatch.setattr(steam, "review_counts", counts)
    return calls


def test_the_saved_pick_is_reused_when_other_games_become_eligible(tmp_path, monkeypatch):
    rows = [game(i, i % 2 == 0) for i in range(1, 41)]
    history(tmp_path, rows)
    _fake(monkeypatch)
    args = ["--data-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--games", "10", "--today", "2026-10-20"]
    sl.main(args + ["--budget-minutes", "0"])  # picks and saves, counts nothing
    first = [r["appid"] for r in storage.read_csv(tmp_path / "history" / "language_sample_games.csv")]
    history(tmp_path, rows + [game(i, i % 2 == 0) for i in range(41, 81)])  # a later day: more eligible games
    assert sl.main(args) == 0
    counted = {r["appid"] for r in storage.read_csv(tmp_path / "history" / "reviews_by_language.csv")}
    assert counted == set(first) and len(first) == 10


def test_a_game_without_any_data_is_not_asked_per_language(tmp_path, monkeypatch):
    history(tmp_path, [game(1, True), game(2, False)])
    calls = _fake(monkeypatch, gone={2})
    sl.main(["--data-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--games", "2", "--today", "2026-10-20"])
    assert [c for c in calls if c[0] == 2] == [(2, "all")]
    rows = [r for r in storage.read_csv(tmp_path / "history" / "reviews_by_language.csv") if r["appid"] == "2"]
    assert len(rows) == len(sl.LANGUAGES) and all(r["reviews"] == "" for r in rows)


def test_work_left_exits_with_3_when_asked(tmp_path, monkeypatch):
    history(tmp_path, [game(1, True), game(2, False)])
    _fake(monkeypatch)
    args = ["--data-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--games", "2", "--today", "2026-10-20",
            "--budget-minutes", "0"]
    assert sl.main(args + ["--fail-if-incomplete"]) == 3
    assert sl.main(args) == 0
