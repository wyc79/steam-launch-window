from types import SimpleNamespace

import pytest

pytest.importorskip("huggingface_hub")
from huggingface_hub.errors import EntryNotFoundError  # noqa: E402

from pipeline import hf_sync  # noqa: E402


class FakeApi:
    def __init__(self, tmp_path, remote: dict[str, str], sha="abc123"):
        self.remote, self.sha, self.dir = remote, sha, tmp_path / "hfcache"
        self.commits = []

    def repo_info(self, repo_id, repo_type=None):
        return SimpleNamespace(sha=self.sha)

    def hf_hub_download(self, repo_id, filename, repo_type=None, revision=None):
        assert revision == self.sha
        if filename not in self.remote:
            raise EntryNotFoundError(f"{filename} not found")
        path = self.dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.remote[filename])
        return str(path)

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


def test_push_commits_every_file_but_dotfiles_with_the_parent(tmp_path):
    src = tmp_path / "gp"
    (src / "followers").mkdir(parents=True)
    (src / "state.csv").write_text("s")
    (src / "followers/2026-10-20.csv.gz").write_text("f")
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
