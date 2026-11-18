"""Windows API fallbacks stay honest and native serving uses the selector loop."""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from labadda import server
from labadda.api import usage
from labadda.health import file_storage, types
from tests.health_support import context


@pytest.mark.parametrize("statistics", [None, SimpleNamespace(f_favail=123), OSError("Unavailable")])
def test_missing_inode_statistics_are_not_fabricated(monkeypatch, tmp_path, statistics):
    monkeypatch.setattr(types.shutil, "disk_usage", lambda path: SimpleNamespace(free=100, total=200))
    if statistics is None:
        monkeypatch.delattr(os, "statvfs", raising=False)
    elif isinstance(statistics, Exception):

        def fail(path):
            raise statistics

        monkeypatch.setattr(os, "statvfs", fail, raising=False)
    else:
        monkeypatch.setattr(os, "statvfs", lambda path: statistics, raising=False)
    reading = types.read_disk(tmp_path)
    assert reading.free_bytes > 0
    assert reading.total_inodes is None
    expected = None if statistics is None or isinstance(statistics, Exception) else 123
    assert reading.free_inodes == expected


def test_unknown_inode_capacity_preserves_byte_reserve_warnings(settings, db_factory):
    ctx = context(settings, db_factory)
    missing = types.DiskReading(50 * 1024**3, 100 * 1024**3, None, None)
    result = file_storage.evaluate(ctx, missing)
    assert result.status == "unknown"
    assert "not measured" in result.detail
    low = types.DiskReading(1024, 100 * 1024**3, None, None)
    assert file_storage.evaluate(ctx, low).status == "unavailable"


def test_windows_serve_uses_selector_and_https_files(monkeypatch):
    run = Mock()
    set_policy = Mock()
    policy = object()
    monkeypatch.setattr(server.sys, "platform", "win32")
    monkeypatch.setattr(asyncio, "WindowsSelectorEventLoopPolicy", lambda: policy, raising=False)
    monkeypatch.setattr(asyncio, "set_event_loop_policy", set_policy)
    monkeypatch.setattr(server.uvicorn, "run", run)
    server.serve("127.0.0.1", 8100, Path("certificate.pem"), Path("private.pem"))
    set_policy.assert_called_once_with(policy)
    assert run.call_args.kwargs["loop"] == "asyncio"
    assert run.call_args.kwargs["ssl_certfile"] == "certificate.pem"
    assert run.call_args.kwargs["ssl_keyfile"] == "private.pem"


def test_linux_serve_keeps_automatic_loop(monkeypatch):
    run = Mock()
    monkeypatch.setattr(server.sys, "platform", "linux")
    monkeypatch.setattr(server.uvicorn, "run", run)
    server.serve("127.0.0.1", 8000, None, None)
    assert run.call_args.kwargs["loop"] == "auto"
    assert run.call_args.kwargs["forwarded_allow_ips"] == "127.0.0.1"


def test_windows_capacity_reports_bytes_without_patching_global_os(monkeypatch, settings):
    monkeypatch.delattr(os, "statvfs", raising=False)
    monkeypatch.setattr(usage.shutil, "disk_usage", lambda path: SimpleNamespace(free=50, total=100))
    value = usage.filesystem_capacity(settings)
    assert value["state"] == "ready"
    assert value["free_bytes"] == 50 and value["total_bytes"] == 100
    assert value["free_inodes"] is None
    assert not hasattr(os, "statvfs")
