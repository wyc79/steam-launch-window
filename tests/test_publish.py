import gzip
import json

import pytest

pd = pytest.importorskip("pandas")
pq = pytest.importorskip("pyarrow.parquet")

from pipeline import publish_dataset as pub  # noqa: E402

EVENTS = """events:
- name: Some Game
  type: major_release
  start: 2026-03-05
  end: 2026-03-05
  on_steam_at_launch: true
  release_kind: full
  steam_appid: 123
  free_to_play: true
  confidence: high
  source: https://example.com
- name: Steam Summer Sale 2026
  type: seasonal_sale
  start: 2026-06-25
  end: 2026-07-09
  confidence: high
  source: https://example.com
- name: Steam Racing Fest 2026
  type: themed_fest
  start: 2026-07-13
  end: 2026-07-20
  tags: [Racing, Driving]
  confidence: high
  source: https://example.com
"""


def write_gz(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(text.encode()))


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    # an old-format day (no price_cents) and a new-format day in the same month
    write_gz(d / "upcoming/snapshots/2026-10-11.csv.gz",
             "appid,release_ts,display,raw,precision,date,date_end,date_ok,early_access,wishlist_rank\n"
             "10,1791993600,date_full,\"Oct 14, 2026\",day,2026-10-14,2026-10-14,1,0,5\n")
    write_gz(d / "upcoming/snapshots/2026-10-12.csv.gz",
             "appid,release_ts,display,raw,precision,date,date_end,date_ok,early_access,wishlist_rank,price_cents\n"
             "10,1791993600,date_full,\"Oct 14, 2026\",day,2026-10-14,2026-10-14,1,0,4,1999\n"
             "11,,text_tba,To be announced,unknown,,,1,0,,\n")
    write_gz(d / "upcoming/snapshots/2026-11-01.csv.gz",
             "appid,release_ts,display,raw,precision,date,date_end,date_ok,early_access,wishlist_rank,price_cents\n"
             "12,,text_tba,To be announced,unknown,,,1,0,,\n")
    (d / "tags.csv").write_text("tagid,name\n492,Indie\n")
    events = tmp_path / "events.yaml"
    events.write_text(EVENTS)
    return d, events


def test_build_groups_days_by_month_with_one_schema(data, tmp_path):
    d, events = data
    out = tmp_path / "out"
    stats = pub.build(d, events, out, "cc-by-4.0")
    assert stats["upcoming/snapshots"] == {"2026-10": 3, "2026-11": 1}
    oct_, nov = (pq.read_schema(out / f"upcoming/snapshots/{m}.parquet") for m in ("2026-10", "2026-11"))
    assert oct_.names == nov.names and "price_cents" in oct_.names and oct_.names[0] == "snapshot_date"
    df = pd.read_parquet(out / "upcoming/snapshots/2026-10.parquet")
    assert df["wishlist_rank"].tolist()[:2] == [5, 4]
    assert pd.isna(df["price_cents"].iloc[0]) and df["price_cents"].iloc[1] == 1999


def test_card_lists_only_configs_with_data(data, tmp_path):
    d, events = data
    out = tmp_path / "out"
    pub.build(d, events, out, "cc-by-4.0")
    card = (out / "README.md").read_text(encoding="utf-8")
    assert "config_name: upcoming_snapshots" in card and "config_name: events" in card
    assert "config_name: history" not in card  # no history file in this fixture
    assert "license: cc-by-4.0" in card


def test_default_card_grants_no_data_license(data, tmp_path, monkeypatch):
    d, events = data
    out = tmp_path / "out"
    monkeypatch.setenv("HF_TOKEN", "x")
    monkeypatch.setattr(pub, "upload", lambda *a, **k: pytest.fail("a dry run must not upload"))
    assert pub.main(["--data-dir", str(d), "--events", str(events), "--out", str(out), "--dry-run"]) == 0
    card = (out / "README.md").read_text(encoding="utf-8")
    assert "license: other" in card and "license: mit" not in card
    assert "No license is granted here for the data" in card


def test_upload_needs_token(data, tmp_path, monkeypatch):
    d, events = data
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="HF_TOKEN"):
        pub.main(["--data-dir", str(d), "--events", str(events), "--out", str(tmp_path / "o"),
                  "--repo-id", "someone/steam-launch-data"])


def test_events_table_keeps_types(data, tmp_path):
    _, events = data
    df = pub.events_table(events)
    assert str(df["steam_appid"].dtype) == "Int64" and df["steam_appid"].iloc[0] == 123
    assert str(df["on_steam_at_launch"].dtype) == "boolean" and bool(df["on_steam_at_launch"].iloc[0])
    assert df["tags"].iloc[2] == "Racing|Driving"
    assert pd.isna(df["tags"].iloc[1])
    assert pd.isna(df["free_to_play"].iloc[1])  # not a release
    sale = df.iloc[1]
    assert sale["starts_at"] == pd.Timestamp("2026-06-25 17:00", tz="UTC")  # 10:00 PDT
    assert sale["ends_at"] == pd.Timestamp("2026-07-09 17:00", tz="UTC")
    game = df.iloc[0]
    assert game["starts_at"] == pd.Timestamp("2026-03-05 08:00", tz="UTC")  # midnight PST
    assert game["ends_at"] == pd.Timestamp("2026-03-06 08:00", tz="UTC")


def test_paid_releases_get_explicit_false(tmp_path):
    path = tmp_path / "e.yaml"
    path.write_text(EVENTS.replace("  free_to_play: true" + chr(10), ""))
    assert pub.events_table(path)["free_to_play"].iloc[0] == False  # noqa: E712 - pandas boolean


# -- safety and new tables ------------------------------------------------------

def test_build_refuses_to_delete_a_folder_it_did_not_build(data, tmp_path):
    d, events = data
    with pytest.raises(SystemExit, match="not a dataset build"):
        pub.build(d, events, d, "mit")  # --out pointing at the data itself
    assert (d / "tags.csv").exists()


def test_build_can_rebuild_its_own_output(data, tmp_path):
    d, events = data
    out = tmp_path / "out"
    pub.build(d, events, out, "mit")
    pub.build(d, events, out, "mit")
    assert (out / "tags.parquet").exists()


def test_card_date_is_the_newest_data_date_so_rebuilds_are_identical(data, tmp_path):
    d, events = data
    pub.build(d, events, tmp_path / "a", "mit")
    card = (tmp_path / "a" / "README.md").read_text(encoding="utf-8")
    assert "Last update: 2026-11-01." in card


def test_release_changes_lists_first_sightings_changes_and_exits(data, tmp_path):
    d, events = data
    out = tmp_path / "out"
    pub.build(d, events, out, "mit")
    df = pd.read_parquet(out / "upcoming/release_changes.parquet")
    got = [(int(r.appid), str(r.snapshot_date), r.change) for r in df.itertuples()]
    assert got == [(10, "2026-10-11", "first_seen"), (11, "2026-10-12", "first_seen"),
                   (10, "2026-11-01", "left_list"), (11, "2026-11-01", "left_list"),
                   (12, "2026-11-01", "first_seen")]


def test_release_changes_records_a_date_change(tmp_path):
    for day, raw, prec, start, end in [("2026-10-11", "November 2026", "month", "2026-11-01", "2026-11-30"),
                                       ("2026-10-12", "November 2026", "month", "2026-11-01", "2026-11-30"),
                                       ("2026-10-13", "Dec 4, 2026", "day", "2026-12-04", "2026-12-04")]:
        write_gz(tmp_path / f"snaps/{day}.csv.gz", "appid,raw,precision,date,date_end\n"
                 f"10,\"{raw}\",{prec},{start},{end}\n")
    df = pub.release_changes(tmp_path / "snaps")
    last = df.iloc[-1]
    assert (last["change"], last["prev_raw"], last["raw"]) == ("changed", "November 2026", "Dec 4, 2026")
    assert len(df) == 2


def test_runs_table_is_published(data, tmp_path):
    d, events = data
    (d / "upcoming").mkdir(exist_ok=True)
    (d / "upcoming/runs.csv").write_text("date,games,requests,ranking_ok\n2026-10-11,60000,120,1\n")
    stats = pub.build(d, events, tmp_path / "out", "mit")
    assert stats["upcoming/runs.parquet"] == 1


def test_new_columns_are_typed():
    df = pub.typed(pd.DataFrame({"reviews_7d": ["3", ""], "last_seen": ["2026-10-11", ""],
                                 "first_listed": ["2026-10-11", ""], "ranking_ok": ["1", "0"]}))
    assert str(df["reviews_7d"].dtype) == "Int64" and str(df["ranking_ok"].dtype) == "Int64"
    assert str(df["last_seen"].iloc[0]) == "2026-10-11" and pd.isna(df["first_listed"].iloc[1])


def test_manifest_check_blocks_dropped_columns_shrunk_tables_and_missing_files():
    old = {"history/games.parquet": {"rows": 1000, "columns": ["appid", "name"]},
           "upcoming/snapshots/2026-10.parquet": {"rows": 50, "columns": ["appid"]}}
    ok = {"history/games.parquet": {"rows": 990, "columns": ["appid", "name", "new"]},
          "upcoming/snapshots/2026-10.parquet": {"rows": 60, "columns": ["appid"]}}
    assert pub.check_manifest(ok, old) == []
    bad = {"history/games.parquet": {"rows": 900, "columns": ["appid"]}}
    problems = pub.check_manifest(bad, old)
    assert any("dropped columns" in p for p in problems)
    assert any("shrank" in p for p in problems)
    assert any("missing" in p for p in problems)
    assert pub.check_manifest(ok, None) == []  # first upload


def test_build_writes_a_manifest(data, tmp_path):
    d, events = data
    pub.build(d, events, tmp_path / "out", "mit")
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert manifest["upcoming/snapshots/2026-10.parquet"]["rows"] == 3
    assert "snapshot_date" in manifest["upcoming/snapshots/2026-10.parquet"]["columns"]


class FakeHub:
    def __init__(self, tmp_path, remote_manifest=None, exists=True):
        self.tmp, self.remote, self.exists, self.uploads = tmp_path, remote_manifest, exists, []

    def repo_info(self, repo_id, repo_type=None):
        from types import SimpleNamespace

        from huggingface_hub.errors import RepositoryNotFoundError
        if not self.exists:
            raise RepositoryNotFoundError("nope", response=SimpleNamespace(headers={}, request=None))
        return SimpleNamespace(sha="head1")

    def hf_hub_download(self, repo_id, filename, repo_type=None, revision=None):
        from types import SimpleNamespace

        from huggingface_hub.errors import LocalEntryNotFoundError, RemoteEntryNotFoundError
        if self.remote == "network error":
            raise LocalEntryNotFoundError("connection error and the file is not cached")
        if self.remote is None:
            raise RemoteEntryNotFoundError("no manifest", response=SimpleNamespace(headers={}, request=None))
        path = self.tmp / "remote_manifest.json"
        path.write_text(json.dumps(self.remote))
        return str(path)

    def upload_folder(self, **kw):
        self.uploads.append(kw)


def test_upload_names_its_parent_and_skips_the_marker(data, tmp_path):
    d, events = data
    out = tmp_path / "out"
    pub.build(d, events, out, "mit")
    hub = FakeHub(tmp_path)
    pub.upload(out, "me/data", "tok", api=hub)
    assert hub.uploads[0]["parent_commit"] == "head1" and pub.MARKER in hub.uploads[0]["ignore_patterns"]


def test_upload_stops_when_the_check_fails(data, tmp_path):
    d, events = data
    out = tmp_path / "out"
    pub.build(d, events, out, "mit")
    hub = FakeHub(tmp_path, remote_manifest={"history/games.parquet": {"rows": 10, "columns": ["appid"]}})
    with pytest.raises(SystemExit, match="missing from the new build"):
        pub.upload(out, "me/data", "tok", api=hub)
    assert hub.uploads == []


def test_upload_needs_an_existing_dataset(data, tmp_path):
    d, events = data
    out = tmp_path / "out"
    pub.build(d, events, out, "mit")
    with pytest.raises(SystemExit, match="create it"):
        pub.upload(out, "me/data", "tok", api=FakeHub(tmp_path, exists=False))


def test_upload_does_not_skip_the_check_on_a_network_error(data, tmp_path):
    from huggingface_hub.errors import LocalEntryNotFoundError
    d, events = data
    out = tmp_path / "out"
    pub.build(d, events, out, "mit")
    hub = FakeHub(tmp_path, remote_manifest="network error")
    with pytest.raises(LocalEntryNotFoundError):
        pub.upload(out, "me/data", "tok", api=hub)
    assert hub.uploads == []


def test_release_changes_marks_a_game_that_comes_back_as_returned(tmp_path):
    rows = {"2026-10-11": "10,Oct 30 2026,day,2026-10-30,2026-10-30\n",
            "2026-10-12": "11,TBA,unknown,,\n",
            "2026-10-13": "10,Oct 30 2026,day,2026-10-30,2026-10-30\n"}
    for day, row in rows.items():
        write_gz(tmp_path / f"snaps/{day}.csv.gz", "appid,raw,precision,date,date_end\n" + row)
    df = pub.release_changes(tmp_path / "snaps")
    assert [(int(r.appid), r.change) for r in df.itertuples()] == [
        (10, "first_seen"), (10, "left_list"), (11, "first_seen"), (10, "returned"), (11, "left_list")]
