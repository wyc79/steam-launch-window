"""Summarize review languages for the saved 1,000-game sample."""

from __future__ import annotations

import argparse
import csv
import math
from collections.abc import Iterable
from pathlib import Path
from statistics import median


LANGUAGES = (
    "english",
    "schinese",
    "tchinese",
    "russian",
    "japanese",
    "koreana",
    "brazilian",
    "german",
    "french",
    "spanish",
)

LABELS = {
    "english": "English",
    "schinese": "Simplified Chinese",
    "tchinese": "Traditional Chinese",
    "russian": "Russian",
    "japanese": "Japanese",
    "koreana": "Korean",
    "brazilian": "Portuguese (Brazil)",
    "german": "German",
    "french": "French",
    "spanish": "Spanish (Spain)",
    "other": "Other",
}

EPSILON = 1e-9  # as site/src/timing.js, so a stored 0.0125 (0.01249...) rounds up


def percent(x: float) -> str:
    """A share with one decimal, rounded half up like the site's percentOf."""
    return f"{math.floor(x * 1000 + 0.5 + EPSILON) / 10:.1f}%"


def load_language_files(data_dir: str | Path) -> tuple[list[dict[str, str]], set[int]]:
    history = Path(data_dir) / "history"
    with (history / "reviews_by_language.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with (history / "language_sample_games.csv").open(newline="", encoding="utf-8") as f:
        appids = {int(row["appid"]) for row in csv.DictReader(f)}
    return rows, appids


def summarize_languages(
    review_rows: Iterable[dict[str, str]], sample_appids: set[int]
) -> dict[bool, dict[str, dict[str, float]]]:
    games: dict[int, dict[str, object]] = {}
    for row in review_rows:
        appid = int(row["appid"])
        if appid not in sample_appids:
            continue
        language = row["language"]
        if language != "all" and language not in LANGUAGES:
            raise ValueError(f"unknown language {language!r} for appid {appid}")
        try:
            supported = {"0": False, "1": True}[row["schinese_supported"]]
        except KeyError as exc:
            raise ValueError(f"invalid Simplified Chinese support flag for appid {appid}") from exc
        reviews = int(row["reviews"])
        if reviews < 0:
            raise ValueError(f"negative review count for appid {appid}")

        game = games.setdefault(appid, {"supported": supported, "counts": {}})
        if game["supported"] != supported:
            raise ValueError(f"support flag changed for appid {appid}")
        counts = game["counts"]
        assert isinstance(counts, dict)
        if language in counts:
            raise ValueError(f"duplicate {language} row for appid {appid}")
        counts[language] = reviews

    missing = sorted(sample_appids - games.keys())
    for appid, game in games.items():
        counts = game["counts"]
        assert isinstance(counts, dict)
        if "all" not in counts:
            missing.append(appid)
    if missing:
        raise ValueError(f"missing all reviews for appid {', '.join(map(str, sorted(set(missing))))}")

    grouped: dict[bool, list[dict[str, int]]] = {False: [], True: []}
    for appid, game in games.items():
        counts = game["counts"]
        assert isinstance(counts, dict)
        total = counts["all"]
        if total <= 0:
            raise ValueError(f"all reviews must be positive for appid {appid}")
        named = {language: counts.get(language, 0) for language in LANGUAGES}
        if any(value > total for value in named.values()) or sum(named.values()) > total:
            raise ValueError(f"language reviews exceed all reviews for appid {appid}")
        named["other"] = total - sum(named.values())
        named["all"] = total
        grouped[bool(game["supported"])].append(named)

    result: dict[bool, dict[str, dict[str, float]]] = {}
    for supported, rows in grouped.items():
        if not rows:
            continue
        total = sum(row["all"] for row in rows)
        result[supported] = {
            language: {
                "pooled": sum(row[language] for row in rows) / total,
                "median": median(row[language] / row["all"] for row in rows),
            }
            for language in (*LANGUAGES, "other")
        }
    return result


def markdown_table(summary: dict[bool, dict[str, dict[str, float]]]) -> str:
    """One narrow table per group, so each fits a phone screen."""
    tables = []
    for supported in (True, False):
        group = "With Simplified Chinese" if supported else "Without Simplified Chinese"
        lines = [f"| {group} | Pooled share | Median per game |", "|---|---:|---:|"]
        for language in (*LANGUAGES, "other"):
            value = summary[supported][language]
            lines.append(f"| {LABELS[language]} | {percent(value['pooled'])} | {percent(value['median'])} |")
        tables.append("\n".join(lines))
    return "\n\n".join(tables)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, appids = load_language_files(args.data_dir)
    print(markdown_table(summarize_languages(rows, appids)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
