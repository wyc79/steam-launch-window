"""Move a working folder to and from a Hugging Face dataset, for collectors that
keep their data there (Games Popularity, under gp/ in the public dataset).

    python -m pipeline.hf_sync pull --repo user/name --dest _hf --require gp/state.csv --file gp/runs.csv
    python -m pipeline.hf_sync push --repo user/name --src _hf --message "gp 2026-10-20"
    python -m pipeline.hf_sync fetch --repo user/name --dest _hf --glob "gp/followers/*.csv.gz"

pull downloads the named files that exist (missing --file ones are skipped, a
missing --require one stops it) from the current revision and writes that
revision to .hf_parent. push commits every file under the folder except
dotfiles and .tmp files, with .hf_parent as the parent commit, so a write made by someone else
in between makes the push fail instead of being overwritten. push refuses to run
without .hf_parent. pull refuses a folder that already has files. Unchanged
files are left out of the commit by huggingface_hub.
fetch downloads every file matching a pattern (at --revision, default the
current one) into a folder, keeping files already there; it fails when nothing
matches, unless --allow-none. pull and push need HF_TOKEN; fetch reads a public
dataset without one. Downloads are copied in through a .tmp file, so a killed
run leaves no half-written file for push to send.
"""

from __future__ import annotations

import argparse
import fnmatch
import logging
import os
import shutil
from pathlib import Path

from huggingface_hub.errors import RemoteEntryNotFoundError

PARENT_FILE = ".hf_parent"
REPO_TYPE = "dataset"

log = logging.getLogger("hf_sync")


def pull(api, repo_id: str, names: list[str], dest: Path, required: list[str] = ()) -> str:
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty: pull into an empty folder, so push sends only this run's files")
    dest.mkdir(parents=True, exist_ok=True)
    sha = api.repo_info(repo_id, repo_type=REPO_TYPE).sha
    for name in [*required, *names]:
        try:
            path = api.hf_hub_download(repo_id, name, repo_type=REPO_TYPE, revision=sha)
        except RemoteEntryNotFoundError:  # really absent; a network error (LocalEntryNotFoundError) must fail
            if name in required:
                # no .hf_parent is written, so a later push refuses to run
                raise SystemExit(f"{name} is not in {repo_id}: refusing to start from nothing") from None
            log.info("%s: not in %s yet", name, repo_id)
            continue
        _place(path, dest / name)
    (dest / PARENT_FILE).write_text(sha)
    return sha


def _place(path: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")  # push skips .tmp files
    shutil.copyfile(path, tmp)
    tmp.replace(target)


def fetch(api, repo_id: str, pattern: str, dest: Path, revision: str | None = None,
          allow_none: bool = False) -> list[str]:
    """Download every file matching `pattern` (fnmatch, so `*` also matches `/`)."""
    revision = revision or api.repo_info(repo_id, repo_type=REPO_TYPE).sha
    names = sorted(n for n in api.list_repo_files(repo_id, repo_type=REPO_TYPE, revision=revision)
                   if fnmatch.fnmatchcase(n, pattern))
    if not names:
        if allow_none:
            log.info("no file in %s matches %s yet", repo_id, pattern)
            return []
        raise SystemExit(f"no file in {repo_id} matches {pattern}")
    for name in names:
        target = dest / name
        if target.exists():  # pulled already, at the same revision
            continue
        _place(api.hf_hub_download(repo_id, name, repo_type=REPO_TYPE, revision=revision), target)
    log.info("fetched %d files matching %s", len(names), pattern)
    return names


def push(api, repo_id: str, src: Path, message: str) -> None:
    from huggingface_hub import CommitOperationAdd

    files = sorted(p for p in src.rglob("*")  # .tmp: left by a write killed before its rename
                   if p.is_file() and p.suffix != ".tmp"
                   and not any(part.startswith(".") for part in p.relative_to(src).parts))
    if not files:
        log.info("nothing to push")
        return
    if not (src / PARENT_FILE).exists():
        raise SystemExit(f"no {PARENT_FILE} in {src}: run pull first, so the push cannot overwrite newer data")
    parent = (src / PARENT_FILE).read_text().strip()
    ops = [CommitOperationAdd(path_in_repo=p.relative_to(src).as_posix(), path_or_fileobj=str(p)) for p in files]
    api.create_commit(repo_id, ops, commit_message=message, repo_type=REPO_TYPE, parent_commit=parent)
    log.info("pushed %d files to %s", len(files), repo_id)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("pull")
    pl.add_argument("--repo", required=True)
    pl.add_argument("--dest", type=Path, required=True)
    pl.add_argument("--file", action="append", default=[], help="download if it exists")
    pl.add_argument("--require", action="append", default=[], help="download, and stop if it does not exist")
    ps = sub.add_parser("push")
    ps.add_argument("--repo", required=True)
    ps.add_argument("--src", type=Path, required=True)
    ps.add_argument("--message", required=True)
    fe = sub.add_parser("fetch")
    fe.add_argument("--repo", required=True)
    fe.add_argument("--dest", type=Path, required=True)
    fe.add_argument("--glob", required=True, help="e.g. gp/followers/*.csv.gz (* also matches /)")
    fe.add_argument("--revision", default=None, help="default: the current revision")
    fe.add_argument("--allow-none", action="store_true", help="exit 0 when no file matches (a new dataset)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.environ.get("HF_TOKEN")
    if not token and args.cmd != "fetch":
        raise SystemExit("set HF_TOKEN")
    from huggingface_hub import HfApi

    api = HfApi(token=token or None)
    if args.cmd == "pull":
        pull(api, args.repo, args.file, args.dest, args.require)
    elif args.cmd == "fetch":
        fetch(api, args.repo, args.glob, args.dest, args.revision, args.allow_none)
    else:
        push(api, args.repo, args.src, args.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
