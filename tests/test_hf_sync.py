from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("huggingface_hub")
from huggingface_hub.errors import LocalEntryNotFoundError, RemoteEntryNotFoundError  # noqa: E402

from pipeline import hf_sync  # noqa: E402


class FakeApi:
    def __init__(self, tmp_path, remote: dict[str, str], sha="abc123"):
        self.remote, self.sha, self.dir = remote, sha, tmp_path / "hfcache"
        self.broken = None
        self.listing_error = None
        self.commits = []

    def repo_info(self, repo_id, repo_type=None):
        return SimpleNamespace(sha=self.sha)

    def hf_hub_download(self, repo_id, filename, repo_type=None, revision=None):
        assert revision == self.sha
        if filename == self.broken:
            raise LocalEntryNotFoundError("connection error and the file is not cached")
        if filename not in self.remote:
            raise RemoteEntryNotFoundError(f"{filename} not found", response=SimpleNamespace(headers={}, request=None))
        path = self.dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.remote[filename])
        return str(path)

    def list_repo_files(self, repo_id, repo_type=None, revision=None):
        assert revision == self.sha
        if self.listing_error:
            raise self.listing_error
        return list(self.remote)

    def create_commit(self, repo_id, operations, *, commit_message, repo_type=None, parent_commit=None):
        self.commits.append({"paths": sorted(op.path_in_repo for op in operations),
                             "message": commit_message, "parent": parent_commit})


def test_pull_copies_files_that_exist_and_records_the_revision(tmp_path):
    api = FakeApi(tmp_path, {"state.csv": "a", "followers/2026-10-20.csv.gz": "b"})
    dest = tmp_path / "gp"
    hf_sync.pull(api, "me/data", ["state.csv", "runs.csv", "followers/2026-10-20.csv.gz"], dest)
    assert (dest / "state.csv").read_text() == "a"
    assert (dest / "followers/2026-10-20.csv.gz").read_text() == "b"
    assert not (dest / "runs.csv").exists()
    assert (dest / hf_sync.PARENT_FILE).read_text() == "abc123"


def test_push_commits_every_file_but_dotfiles_and_tmp_with_the_parent(tmp_path):
    src = tmp_path / "gp"
    (src / "followers").mkdir(parents=True)
    (src / "state.csv").write_text("s")
    (src / "followers/2026-10-20.csv.gz").write_text("f")
    (src / "state.csv.tmp").write_text("half-written")
    (src / hf_sync.PARENT_FILE).write_text("abc123")
    api = FakeApi(tmp_path, {})
    hf_sync.push(api, "me/data", src, "gp 2026-10-20")
    assert api.commits == [{"paths": ["followers/2026-10-20.csv.gz", "state.csv"],
                            "message": "gp 2026-10-20", "parent": "abc123"}]


def test_push_with_nothing_to_send_makes_no_commit(tmp_path):
    src = tmp_path / "gp"
    src.mkdir()
    api = FakeApi(tmp_path, {})
    hf_sync.push(api, "me/data", src, "msg")
    assert api.commits == []


def test_cli_needs_a_token(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="HF_TOKEN"):
        hf_sync.main(["push", "--repo", "me/data", "--src", str(tmp_path), "--message", "m"])


def test_push_refuses_without_a_pulled_parent(tmp_path):
    src = tmp_path / "gp"
    src.mkdir()
    (src / "state.csv").write_text("partial")
    api = FakeApi(tmp_path, {})
    with pytest.raises(SystemExit, match="pull"):
        hf_sync.push(api, "me/data", src, "msg")
    assert api.commits == []


def test_pull_fails_on_a_network_error_instead_of_treating_the_file_as_missing(tmp_path):
    api = FakeApi(tmp_path, {"state.csv": "a"})
    api.broken = "state.csv"
    dest = tmp_path / "gp"
    with pytest.raises(LocalEntryNotFoundError):
        hf_sync.pull(api, "me/data", ["state.csv"], dest)
    assert not (dest / hf_sync.PARENT_FILE).exists()  # so a later push refuses to run


def test_pull_stops_when_a_required_file_is_missing(tmp_path):
    api = FakeApi(tmp_path, {"gp/runs.csv": "r"})
    dest = tmp_path / "hf"
    with pytest.raises(SystemExit, match="gp/state.csv"):
        hf_sync.pull(api, "me/data", ["gp/runs.csv"], dest, required=["gp/state.csv"])
    assert not (dest / hf_sync.PARENT_FILE).exists()  # so a later push refuses to run


def test_pull_downloads_required_files_into_their_folders(tmp_path):
    api = FakeApi(tmp_path, {"gp/state.csv": "s"})
    dest = tmp_path / "hf"
    hf_sync.pull(api, "me/data", ["gp/runs.csv"], dest, required=["gp/state.csv"])
    assert (dest / "gp/state.csv").read_text() == "s"
    assert (dest / hf_sync.PARENT_FILE).read_text() == "abc123"


def test_pull_refuses_a_folder_that_already_has_files(tmp_path):
    dest = tmp_path / "gp"
    (dest / "followers").mkdir(parents=True)
    (dest / "followers" / "2026-01-01.csv.gz").write_text("stale")
    with pytest.raises(SystemExit, match="not empty"):
        hf_sync.pull(FakeApi(tmp_path, {}), "me/data", ["state.csv"], dest)


def test_fetch_downloads_every_matching_file_and_keeps_pulled_ones(tmp_path):
    remote = {"gp/state.csv": "s", "gp/followers/2026-10-12.csv.gz": "a", "gp/followers/2026-10-13.csv.gz": "b",
              "gp/players/2026-10-13.csv.gz": "p"}
    api = FakeApi(tmp_path, remote)
    dest = tmp_path / "hf"
    hf_sync.pull(api, "me/data", ["gp/followers/2026-10-13.csv.gz"], dest, required=["gp/state.csv"])
    (dest / "gp/followers/2026-10-13.csv.gz").write_text("changed by this run")
    got = hf_sync.fetch(api, "me/data", "gp/followers/*.csv.gz", dest, revision="abc123")
    assert got == ["gp/followers/2026-10-12.csv.gz", "gp/followers/2026-10-13.csv.gz"]
    assert (dest / "gp/followers/2026-10-12.csv.gz").read_text() == "a"
    assert (dest / "gp/followers/2026-10-13.csv.gz").read_text() == "changed by this run"
    assert not (dest / "gp/players").exists()


def test_fetch_fails_when_nothing_matches(tmp_path):
    with pytest.raises(SystemExit, match="matches"):
        hf_sync.fetch(FakeApi(tmp_path, {"gp/state.csv": "s"}), "me/data", "gp/followers/*.csv.gz", tmp_path / "x")


def test_fetch_allow_none_accepts_no_match_but_not_an_error(tmp_path):
    api = FakeApi(tmp_path, {"gp/state.csv": "s"})
    assert hf_sync.fetch(api, "me/data", "gp/followers/*.csv.gz", tmp_path / "x", allow_none=True) == []
    api.listing_error = ConnectionError("network down")
    with pytest.raises(ConnectionError):
        hf_sync.fetch(api, "me/data", "gp/followers/*.csv.gz", tmp_path / "x", allow_none=True)


def test_a_killed_copy_leaves_no_half_written_file_for_push(tmp_path, monkeypatch):
    def killed(src, dst):
        Path(dst).write_text("half")
        raise KeyboardInterrupt

    monkeypatch.setattr(hf_sync.shutil, "copyfile", killed)
    dest = tmp_path / "hf"
    with pytest.raises(KeyboardInterrupt):
        hf_sync.pull(FakeApi(tmp_path, {"gp/state.csv": "s"}), "me/data", [], dest, required=["gp/state.csv"])
    assert not (dest / "gp/state.csv").exists() and (dest / "gp/state.csv.tmp").exists()
    (dest / hf_sync.PARENT_FILE).write_text("abc123")
    api = FakeApi(tmp_path, {})
    hf_sync.push(api, "me/data", dest, "msg")
    assert api.commits == []


def test_cli_fetch_needs_no_token(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    seen = {}
    monkeypatch.setattr(hf_sync, "fetch", lambda api, repo, pattern, dest, revision, allow_none: seen.update(
        repo=repo, pattern=pattern, revision=revision, allow_none=allow_none))
    assert hf_sync.main(["fetch", "--repo", "me/data", "--dest", str(tmp_path), "--glob", "gp/followers/*"]) == 0
    assert seen == {"repo": "me/data", "pattern": "gp/followers/*", "revision": None, "allow_none": False}
    assert hf_sync.main(["fetch", "--repo", "me/data", "--dest", str(tmp_path), "--glob", "gp/followers/*",
                         "--allow-none"]) == 0
    assert seen["allow_none"] is True
