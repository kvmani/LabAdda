"""Transient board content obeys current access, even without a revocation signal."""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from labadda.realtime import Connection, Hub


class Socket:
    """Collect content and close notices without transport timing."""

    def __init__(self):
        self.messages = []

    async def send_text(self, value):
        import json

        self.messages.append(json.loads(value))

    async def close(self, code):
        pass


def scenario(settings, sender_decision, receiver_decision, *, change_generation=False):
    async def run():
        workspace = uuid.uuid4()
        hub = Hub(None, settings)
        sender = Connection(Socket(), uuid.uuid4(), "sender", "Sender")
        receiver = Connection(Socket(), uuid.uuid4(), "receiver", "Receiver")
        hub.connections.update([sender, receiver])
        for conn in (sender, receiver):
            conn.subscriptions.add(workspace)
            conn.writable.add(workspace)

        def check(conn, workspaces):
            if change_generation:
                conn.subscription_generations[workspace] = 1
            ok, readable, writable = sender_decision
            return ok, {workspace} if readable else set(), {workspace} if writable else set()

        hub._check = check
        hub._check_many = lambda conns, ws: dict.fromkeys(conns, receiver_decision)
        await hub._handle(
            sender,
            {"type": "board.preview", "workspace_id": str(workspace), "stroke": {"points": [[1, 2]]}},
        )
        return SimpleNamespace(sender=sender, receiver=receiver, hub=hub, workspace=workspace)

    return asyncio.run(run())


@pytest.mark.parametrize("decision", [(False, False, False), (True, False, False), (True, True, False)])
def test_preview_rechecks_sender(settings, decision):
    result = scenario(settings, decision, (True, True, True))
    assert not any(msg["type"] == "board.preview" for msg in result.receiver.ws.messages)
    assert result.workspace not in result.sender.writable


@pytest.mark.parametrize("decision", [(False, False, False), (True, False, False)])
def test_preview_rechecks_recipient(settings, decision):
    result = scenario(settings, (True, True, True), decision)
    assert not any(msg["type"] == "board.preview" for msg in result.receiver.ws.messages)
    if not decision[0]:
        assert result.receiver not in result.hub.connections
    else:
        assert result.workspace not in result.receiver.subscriptions


def test_preview_cannot_cross_sender_subscription_generation(settings):
    result = scenario(settings, (True, True, True), (True, True, True), change_generation=True)
    assert not any(msg["type"] == "board.preview" for msg in result.receiver.ws.messages)


def test_preview_reaches_current_reader_without_echo(settings):
    result = scenario(settings, (True, True, True), (True, True, False))
    messages = [msg for msg in result.receiver.ws.messages if msg["type"] == "board.preview"]
    assert len(messages) == 1
    assert messages[0]["stroke"] == {"points": [[1, 2]]}
    assert not any(msg["type"] == "board.preview" for msg in result.sender.ws.messages)


@pytest.mark.parametrize("invalid_session", [False, True])
def test_presence_excludes_stale_members_and_recipients(settings, invalid_session):
    async def run():
        workspace = uuid.uuid4()
        hub = Hub(None, settings)
        stale = Connection(Socket(), uuid.uuid4(), "stale", "Stale")
        current = Connection(Socket(), uuid.uuid4(), "current", "Current")
        hub.connections.update([stale, current])
        for conn in (stale, current):
            conn.subscriptions.add(workspace)
        hub._check_many = lambda conns, ws: {
            conn: (not invalid_session, False, False) if conn is stale else (True, True, True)
            for conn in conns
        }
        await hub._presence(workspace)
        assert not any(message["type"] == "presence" for message in stale.ws.messages)
        messages = [message for message in current.ws.messages if message["type"] == "presence"]
        assert messages[-1]["users"] == [{"id": str(current.user_id), "display_name": "Current"}]

    asyncio.run(run())


@pytest.mark.parametrize("role", ["sender", "receiver"])
@pytest.mark.parametrize("loss", ["expired", "idle", "revoked", "membership", "read_only"])
def test_preview_uses_current_database_access(as_user, ids, settings, app, *, role, loss):
    from datetime import timedelta

    from sqlalchemy import delete

    from labadda.models import AuthSession, Membership, Workspace
    from labadda.security import digest, utcnow

    sender_api, receiver_api = as_user("ben"), as_user("asha")
    workspace = uuid.UUID(ids["workspaces"]["section_a"])
    sender = Connection(
        Socket(),
        uuid.UUID(ids["users"]["ben"]),
        digest(sender_api.client.cookies.get(settings.cookie_name)),
        "Sender",
    )
    receiver = Connection(
        Socket(),
        uuid.UUID(ids["users"]["asha"]),
        digest(receiver_api.client.cookies.get(settings.cookie_name)),
        "Receiver",
    )
    target = sender if role == "sender" else receiver
    with app.state.session_factory() as db:
        session = db.get(AuthSession, target.session_id)
        if loss == "expired":
            session.expires_at = utcnow() - timedelta(seconds=1)
        elif loss == "idle":
            session.last_seen_at = utcnow() - timedelta(minutes=settings.session_idle_minutes + 1)
        elif loss == "revoked":
            session.revoked_at = utcnow()
        elif loss == "membership":
            db.execute(
                delete(Membership).where(
                    Membership.user_id == target.user_id,
                    Membership.workspace_id == workspace,
                )
            )
        else:
            db.get(Workspace, workspace).archived = True
        db.commit()
    hub = app.state.hub
    hub.connections.update([sender, receiver])
    for conn in (sender, receiver):
        conn.subscriptions.add(workspace)
        conn.writable.add(workspace)
    asyncio.run(
        hub._handle(
            sender,
            {
                "type": "board.preview",
                "workspace_id": str(workspace),
                "stroke": {"points": [[1, 2]]},
            },
        )
    )
    assert not any(message["type"] == "board.preview" for message in receiver.ws.messages)


def test_slow_stale_connection_does_not_delay_healthy_presence(settings):
    async def run():
        workspace = uuid.uuid4()
        hub = Hub(None, settings)
        stale = Connection(Socket(), uuid.uuid4(), "stale", "Stale")
        current = Connection(Socket(), uuid.uuid4(), "current", "Current")
        hub.connections.update([stale, current])
        for conn in (stale, current):
            conn.subscriptions.add(workspace)
        hub._check_many = lambda conns, ws: {
            conn: (False, False, False) if conn is stale else (True, True, True) for conn in conns
        }
        release, delivered = asyncio.Event(), asyncio.Event()
        original_close, original_send = hub._close, hub._send

        async def slow_close(conn, reason, **kwargs):
            await release.wait()
            await original_close(conn, reason, **kwargs)

        async def send(conn, payload, **kwargs):
            await original_send(conn, payload, **kwargs)
            if conn is current and payload["type"] == "presence":
                delivered.set()

        hub._close, hub._send = slow_close, send
        task = asyncio.create_task(hub._presence(workspace))
        try:
            await asyncio.wait_for(delivered.wait(), timeout=1)
        finally:
            release.set()
            await task
        assert current.ws.messages[-1]["users"] == [{"id": str(current.user_id), "display_name": "Current"}]

    asyncio.run(run())
