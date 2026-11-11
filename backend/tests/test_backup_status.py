"""The shared backup status schema: validation, atomic writes and the bounded reader."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from labadda import backup_status as bs

NOW = datetime(2026, 11, 11, 2, 30, tzinfo=UTC)


def success(**changes) -> bs.BackupStatus:
    values = {
        "finished_at": NOW,
        "result": "success",
        "size_bytes": 12345,
        "verification": "passed",
        "destination": "local",
        "schema": "0025",
        "release": "r2026-11-11",
    }
    values.update(changes)
    return bs.BackupStatus(**values)


def failure(**changes) -> bs.BackupStatus:
    values = {
        "result": "failure",
        "size_bytes": None,
        "verification": "not_run",
        "schema": None,
        "release": None,
    }
    values.update(changes)
    return success(**values)


def test_success_record_round_trips_through_the_shared_schema(tmp_path):
    bs.write_status(tmp_path, success())

    reading = bs.read_status(tmp_path)

    assert reading.state == "ok"
    assert reading.status == success()


def test_failure_record_round_trips_and_has_no_size(tmp_path):
    bs.write_status(tmp_path, failure())

    reading = bs.read_status(tmp_path)

    assert reading.state == "ok"
    assert reading.status.result == "failure"
    assert reading.status.size_bytes is None


def test_written_file_holds_only_documented_fields_and_no_paths(tmp_path):
    bs.write_status(tmp_path, success())

    record = json.loads((tmp_path / bs.STATUS_FILENAME).read_text())

    assert set(record) == bs.FIELDS
    assert str(tmp_path) not in json.dumps(record)
    assert (tmp_path / bs.STATUS_FILENAME).stat().st_mode & 0o777 == 0o644


def test_missing_file_reads_as_unknown(tmp_path):
    assert bs.read_status(tmp_path).state == "unknown"
    assert bs.read_status(None).state == "unknown"


def test_oversized_file_is_rejected(tmp_path):
    record = success().as_record()
    record["padding"] = "x" * bs.MAX_STATUS_BYTES
    (tmp_path / bs.STATUS_FILENAME).write_text(json.dumps(record))

    assert bs.read_status(tmp_path).state == "invalid"


@pytest.mark.parametrize(
    "content",
    ["", "not json", "[]", "null", "[" * 5000, '{"format": 1}', "\x00\x01"],
)
def test_malformed_file_is_rejected(tmp_path, content):
    (tmp_path / bs.STATUS_FILENAME).write_text(content)

    assert bs.read_status(tmp_path).state == "invalid"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format", 2),
        ("format", True),
        ("finished_at", "2026-11-11 02:30:00"),
        ("finished_at", "2026-13-45T99:00:00Z"),
        ("result", "ok"),
        ("size_bytes", -1),
        ("size_bytes", "12"),
        ("size_bytes", True),
        ("verification", "maybe"),
        ("destination", "/srv/labadda-backups"),
        ("destination", "backup-host.example.test"),
        ("schema", "../0025"),
        ("release", "/srv/labadda/releases/r1"),
    ],
)
def test_invalid_field_values_are_rejected(tmp_path, field, value):
    record = success().as_record()
    record[field] = value
    (tmp_path / bs.STATUS_FILENAME).write_text(json.dumps(record))

    assert bs.read_status(tmp_path).state == "invalid"


def test_unknown_and_missing_fields_are_rejected(tmp_path):
    extra = {**success().as_record(), "path": "/srv/x"}
    missing = success().as_record()
    del missing["release"]
    for record in (extra, missing):
        (tmp_path / bs.STATUS_FILENAME).write_text(json.dumps(record))
        assert bs.read_status(tmp_path).state == "invalid"


def test_inconsistent_results_cannot_be_written(tmp_path):
    with pytest.raises(bs.StatusError):
        bs.write_status(tmp_path, success(verification="failed"))
    with pytest.raises(bs.StatusError):
        bs.write_status(tmp_path, success(size_bytes=None))
    with pytest.raises(bs.StatusError):
        bs.write_status(tmp_path, failure(verification="passed"))
    assert not (tmp_path / bs.STATUS_FILENAME).exists()


def test_symlinked_status_file_is_rejected(tmp_path):
    target = tmp_path / "elsewhere.json"
    target.write_bytes(bs.encode(success()))
    directory = tmp_path / "status"
    directory.mkdir()
    (directory / bs.STATUS_FILENAME).symlink_to(target)

    assert bs.read_status(directory).state == "invalid"


def test_failed_fsync_leaves_the_previous_file_intact(tmp_path):
    bs.write_status(tmp_path, success())
    before = (tmp_path / bs.STATUS_FILENAME).read_bytes()

    with patch.object(bs.os, "fsync", side_effect=OSError("disk gone")), pytest.raises(OSError):
        bs.write_status(tmp_path, failure())

    assert (tmp_path / bs.STATUS_FILENAME).read_bytes() == before
    assert list(tmp_path.glob(".backup-status-*")) == []


def test_crash_before_rename_leaves_the_previous_file_intact(tmp_path):
    bs.write_status(tmp_path, success())
    before = (tmp_path / bs.STATUS_FILENAME).read_bytes()

    with patch.object(bs.os, "replace", side_effect=KeyboardInterrupt), pytest.raises(KeyboardInterrupt):
        bs.write_status(tmp_path, failure())

    assert (tmp_path / bs.STATUS_FILENAME).read_bytes() == before
    assert bs.read_status(tmp_path).status == success()


def test_leftover_temporary_file_from_a_hard_crash_is_ignored(tmp_path):
    bs.write_status(tmp_path, success())
    (tmp_path / ".backup-status-abandoned.tmp").write_text("{half a file")

    assert bs.read_status(tmp_path).status == success()


def test_a_new_write_replaces_the_old_one(tmp_path):
    bs.write_status(tmp_path, success())
    bs.write_status(tmp_path, failure(finished_at=NOW + timedelta(hours=24)))

    reading = bs.read_status(tmp_path)

    assert reading.status.result == "failure"
    assert list(tmp_path.iterdir()) == [tmp_path / bs.STATUS_FILENAME]


def test_age_is_negative_for_a_future_timestamp():
    assert bs.age(success(), NOW + timedelta(hours=3)) == timedelta(hours=3)
    assert bs.age(success(finished_at=NOW + timedelta(hours=1)), NOW) < timedelta(0)


def test_directory_fsync_is_attempted(tmp_path):
    seen = []
    real = os.fsync

    def recording(descriptor):
        seen.append(descriptor)
        real(descriptor)

    with patch.object(bs.os, "fsync", side_effect=recording):
        bs.write_status(Path(tmp_path), success())

    assert len(seen) == 2
