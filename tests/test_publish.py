import gzip

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
