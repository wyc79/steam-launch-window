import csv

import pytest

from analysis.languages import load_language_files, markdown_table, percent, summarize_languages


def row(appid, chinese, language, reviews):
    return {
        "appid": str(appid),
        "schinese_supported": "1" if chinese else "0",
        "language": language,
        "reviews": str(reviews),
    }


def test_summarize_languages_uses_pooled_totals_and_per_game_medians():
    rows = [
        row(1, True, "all", 100),
        row(1, True, "english", 40),
        row(1, True, "schinese", 20),
        row(2, True, "all", 20),
        row(2, True, "english", 16),
        row(2, True, "schinese", 0),
        row(3, False, "all", 50),
        row(3, False, "english", 40),
        row(3, False, "schinese", 5),
    ]

    got = summarize_languages(rows, {1, 2, 3})

    assert got[True]["english"] == pytest.approx({"pooled": 56 / 120, "median": 0.6})
    assert got[True]["schinese"] == pytest.approx({"pooled": 20 / 120, "median": 0.1})
    assert got[True]["other"] == pytest.approx({"pooled": 44 / 120, "median": 0.3})
    assert got[False]["english"] == pytest.approx({"pooled": 0.8, "median": 0.8})
    assert got[False]["schinese"] == pytest.approx({"pooled": 0.1, "median": 0.1})
    assert got[False]["other"] == pytest.approx({"pooled": 0.1, "median": 0.1})


def test_percent_rounds_half_up_like_the_site():
    # 0.0125 is stored as 0.01249..., which Python's .1% turns into 1.2%
    assert f"{0.0125:.1%}" == "1.2%"
    assert percent(0.0125) == "1.3%"
    assert percent(0.0124) == "1.2%"
    assert percent(0.55) == "55.0%"
    assert percent(0) == "0.0%"


def test_markdown_table_rounds_a_tie_half_up():
    rows = [row(1, True, "all", 2000), row(1, True, "english", 25), row(2, False, "all", 10)]

    table = markdown_table(summarize_languages(rows, {1, 2}))

    with_chinese, without_chinese = table.split("\n\n")
    assert with_chinese.splitlines()[0] == "| With Simplified Chinese | Pooled share | Median per game |"
    assert "| English | 1.3% | 1.3% |" in with_chinese.splitlines()
    assert without_chinese.splitlines()[0] == "| Without Simplified Chinese | Pooled share | Median per game |"
    assert len(without_chinese.splitlines()) == 2 + 11


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([row(1, True, "all", 10), row(1, True, "all", 10)], "duplicate"),
        ([row(1, True, "english", 10)], "missing all"),
        ([row(1, True, "all", 10), row(1, False, "english", 8)], "support flag"),
        ([row(1, True, "all", -1)], "negative"),
        ([row(1, True, "all", 10), row(1, True, "english", 11)], "exceed all"),
    ],
)
def test_summarize_languages_rejects_invalid_rows(rows, message):
    with pytest.raises(ValueError, match=message):
        summarize_languages(rows, {1})


def test_summarize_languages_requires_every_saved_game():
    with pytest.raises(ValueError, match="missing all.*2"):
        summarize_languages([row(1, True, "all", 10)], {1, 2})


def test_load_language_files_reads_only_local_csv(tmp_path):
    history = tmp_path / "history"
    history.mkdir()
    with (history / "language_sample_games.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["appid"])
        writer.writeheader()
        writer.writerow({"appid": "7"})
    with (history / "reviews_by_language.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["appid", "schinese_supported", "language", "reviews"])
        writer.writeheader()
        writer.writerow(row(7, False, "all", 12))

    rows, appids = load_language_files(tmp_path)

    assert rows == [row(7, False, "all", 12)]
    assert appids == {7}
