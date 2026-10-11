"""CSV read/write helpers. Writes are atomic so a killed run never leaves half a file."""

from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path


def _open_text(path: Path, mode: str):
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, mode + "b"), encoding="utf-8", newline="")
    return open(path, mode, encoding="utf-8", newline="")


def read_csv(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with _open_text(path, "r") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: list[dict], fields: list[str]) -> None:
    """Write rows (sorted by the caller) to .csv or .csv.gz atomically.

    Gzip output uses mtime=0 so identical content gives identical bytes.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    data = buf.getvalue().encode("utf-8")
    if path.suffix == ".gz":
        data = gzip.compress(data, mtime=0)
    tmp.write_bytes(data)
    tmp.replace(path)


def append_csv(path: str | Path, row: dict, fields: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow(row)
