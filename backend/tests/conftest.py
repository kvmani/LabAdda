"""Test harness: disposable PostgreSQL database, fictional fixture, per-actor clients."""

from __future__ import annotations

import os
from dataclasses import replace

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from labadda.app import create_app
from labadda.cli import alembic_config
from labadda.config import load_settings
from labadda.db import session_factory
from labadda.fixtures import fixture_password, reset_database, seed
from labadda.security import login_limiter

TEST_DB = os.environ.get(
    "LABADDA_TEST_DATABASE_URL", "postgresql+psycopg://labadda:labadda-dev@localhost:5432/labadda_test"
)


def recreate_schema(url: str) -> None:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


@pytest.fixture(scope="session")
def migrated():
    recreate_schema(TEST_DB)
    command.upgrade(alembic_config(TEST_DB), "head")
    return TEST_DB


@pytest.fixture
def settings(migrated, tmp_path):
    base = load_settings()
    return replace(
        base,
        database_url=migrated,
        environment="test",
        run_scheduler=False,
        asset_dir=tmp_path / "assets",
        base_path=os.environ.get("LABADDA_TEST_BASE_PATH", ""),
        instance="test",
        frontend_dist=None,
    )


@pytest.fixture
def db_factory(settings):
    return session_factory(settings.database_url)


@pytest.fixture
def ids(db_factory):
    login_limiter.reset()
    with db_factory() as db:
        reset_database(db)
        return seed(db)


@pytest.fixture
def app(settings, ids):
    return create_app(settings)


class Api:
    """A signed-in browser-like client for one actor."""

    def __init__(self, client: TestClient, prefix: str):
        self.client = client
        self.prefix = prefix
        self.csrf = None

    def url(self, path: str) -> str:
        return self.prefix + path

    def login(self, username: str, password: str | None = None):
        r = self.client.post(
            self.url("/auth/login"), json={"username": username, "password": password or fixture_password()}
        )
        if r.status_code == 200:
            self.csrf = r.json()["csrf_token"]
        return r

    def _headers(self, extra=None):
        h = {"X-CSRF-Token": self.csrf} if self.csrf else {}
        h.update(extra or {})
        return h

    def get(self, path, **kw):
        return self.client.get(self.url(path), **kw)

    def post(self, path, json=None, headers=None, **kw):
        return self.client.post(self.url(path), json=json, headers=self._headers(headers), **kw)

    def patch(self, path, json=None, headers=None):
        return self.client.patch(self.url(path), json=json, headers=self._headers(headers))

    def put(self, path, json=None, headers=None):
        return self.client.put(self.url(path), json=json, headers=self._headers(headers))

    def delete(self, path, headers=None, **kw):
        return self.client.delete(self.url(path), headers=self._headers(headers), **kw)


@pytest.fixture
def make_client(app, settings):
    clients = []

    def _make(username: str | None = None) -> Api:
        c = TestClient(app)
        clients.append(c)
        api = Api(c, settings.api_prefix)
        if username:
            r = api.login(username)
            assert r.status_code == 200, r.text
        return api

    yield _make
    for c in clients:
        c.close()


@pytest.fixture
def as_user(make_client):
    cache = {}

    def _get(username: str) -> Api:
        if username not in cache:
            cache[username] = make_client(username)
        return cache[username]

    return _get
