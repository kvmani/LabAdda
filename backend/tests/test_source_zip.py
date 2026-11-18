"""Building on the server from GitHub's release zip, which carries no git history."""

import io
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import source_zip  # noqa: E402 — needs the scripts directory on sys.path first

COMMIT = "7b81cf13a89249deab2246b6082e2c775b9da280"


def make_zip(path: Path, entries: dict[str, bytes], comment: str = COMMIT) -> Path:
    with zipfile.ZipFile(path, "w") as bundle:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 17, 18, 48, 25))
            bundle.writestr(info, data)
        bundle.comment = comment.encode()
    return path


def labadda_zip(tmp_path: Path, **extra: bytes) -> Path:
    entries = {"LabAdda-0.1.0-beta/backend/labadda/__init__.py": b'__version__ = "0.1.0-beta"\n'}
    entries |= {f"LabAdda-0.1.0-beta/{name}": data for name, data in extra.items()}
    return make_zip(tmp_path / "release.zip", entries)


def test_identity_is_the_commit_in_the_comment_and_the_entry_date(tmp_path):
    assert source_zip.identity(labadda_zip(tmp_path)) == (COMMIT, "2026-11-17")


def test_a_zip_without_a_commit_is_refused(tmp_path):
    archive = make_zip(tmp_path / "plain.zip", {"x/backend/labadda/__init__.py": b""}, comment="")
    with pytest.raises(source_zip.SourceZipError, match="no commit"):
        source_zip.identity(archive)


@pytest.mark.parametrize("name", ["../evil", "/etc/passwd", "LabAdda/../../evil"])
def test_extract_refuses_entries_that_leave_the_folder(tmp_path, name):
    archive = make_zip(tmp_path / "bad.zip", {name: b"x"})
    with pytest.raises(source_zip.SourceZipError, match="Unsafe"):
        source_zip.extract(archive, tmp_path / "out")
    assert not (tmp_path / "evil").exists()


def test_extract_refuses_a_zip_that_is_not_labadda(tmp_path):
    archive = make_zip(tmp_path / "other.zip", {"project/README.md": b"x"})
    with pytest.raises(source_zip.SourceZipError, match="not a LabAdda"):
        source_zip.extract(archive, tmp_path / "out")


def test_tree_files_matches_git_archive_and_skips_local_state(tmp_path):
    root = source_zip.extract(
        labadda_zip(tmp_path, **{"frontend/src/a.ts": b"1", "frontend/node_modules/x/index.js": b"2"}),
        tmp_path / "out",
    )
    (root / "backend/labadda/__pycache__").mkdir()
    (root / "backend/labadda/__pycache__/x.pyc").write_bytes(b"")
    assert source_zip.tree_files(root) == ["backend/labadda/__init__.py", "frontend/src/a.ts"]


def test_git_archive_of_this_repository_carries_its_commit(tmp_path):
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not installed (for example a server that only receives release zips)")
    # Fixed git subcommands on this checkout, as in build_info.py; no outside input reaches them.
    head = subprocess.run(  # noqa: S603
        [git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if head.returncode:
        pytest.skip("not a git checkout (for example a copy unpacked from a release zip)")
    data = subprocess.run(  # noqa: S603
        [git, "archive", "--format=zip", "HEAD"], cwd=ROOT, capture_output=True, check=True
    )
    archive = tmp_path / "head.zip"
    archive.write_bytes(data.stdout)
    assert source_zip.identity(archive)[0] == head.stdout.strip()
    assert zipfile.ZipFile(io.BytesIO(data.stdout)).comment.decode() == head.stdout.strip()
