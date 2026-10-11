"""Move a working folder to and from a Hugging Face dataset, for collectors that
keep their data there (the private Games Popularity dataset).

    python -m pipeline.hf_sync pull --repo user/name --dest _gp --file state.csv --file runs.csv
    python -m pipeline.hf_sync push --repo user/name --src _gp --message "gp 2026-10-20"

pull downloads the named files that exist (missing ones are skipped) from the
current revision and writes that revision to .hf_parent. push commits every file
under the folder except dotfiles, with .hf_parent as the parent commit, so a
write made by someone else in between makes the push fail instead of being
overwritten. push refuses to run without .hf_parent. Unchanged files are left out of the commit by huggingface_hub.
Needs HF_TOKEN.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
from pathlib import Path

from huggingface_hub.errors import EntryNotFoundError

PARENT_FILE = ".hf_parent"
REPO_TYPE = "dataset"

log = logging.getLogger("hf_sync")


def pull(api, repo_id: str, names: list[str], dest: Path) -> str:
    dest.mkdir(parents=True, exist_ok=True)
    sha = api.repo_info(repo_id, repo_type=REPO_TYPE).sha
    for name in names:
        try:
            path = api.hf_hub_download(repo_id, name, repo_type=REPO_TYPE, revision=sha)
        except EntryNotFoundError:
            log.info("%s: not in %s yet", name, repo_id)
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (dest / PARENT_FILE).write_text(sha)
    return sha


def push(api, repo_id: str, src: Path, message: str) -> None:
    from huggingface_hub import CommitOperationAdd

    files = sorted(p for p in src.rglob("*")
                   if p.is_file() and not any(part.startswith(".") for part in p.relative_to(src).parts))
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
    pl.add_argument("--file", action="append", default=[])
    ps = sub.add_parser("push")
    ps.add_argument("--repo", required=True)
    ps.add_argument("--src", type=Path, required=True)
    ps.add_argument("--message", required=True)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("set HF_TOKEN")
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    if args.cmd == "pull":
        pull(api, args.repo, args.file, args.dest)
    else:
        push(api, args.repo, args.src, args.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
