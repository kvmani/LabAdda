#!/usr/bin/env python3
"""S4 workload rehearsal (T13): many signed-in clients across two sibling workspaces.

Every client signs in and holds a live socket subscribed to its own workspace. A subset draw
on that workspace's board; the rest read the feed and chat, and post chat messages. The
harness then checks, per workspace:

* every acknowledged board operation exists exactly once (retained ops or compacted snapshot)
  with contiguous revisions;
* every client received every committed board operation and chat message of its workspace
  that was acknowledged after it subscribed (delivery completeness);
* no client ever received an event for the other workspace (isolation under load);

and reports committed-update latency over every (event, receiving client) pair, list latency
and request errors. Development/test instances only: it signs in with the fixture admin and
creates synthetic accounts.

    .venv/bin/python scripts/rehearsal.py --synthetic-target --origin https://127.0.0.1:8080 \\
        --cafile var/proxy-stack/tls/ca.crt --clients 30 --drawers 8 --seconds 900 --enforce-targets
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import secrets
import ssl
import statistics
import time
from dataclasses import dataclass, field

import httpx
import websockets
from soak import PASSWORD, login, metric, pct

DEFAULT_WORKSPACES = ("Thin Films Section", "Catalysis Section")


@dataclass
class Client:
    username: str
    workspace: str  # workspace id
    drawer: bool
    subscribed_at: float | None = None
    received: dict[str, float] = field(default_factory=dict)  # event key -> arrival time
    foreign_events: int = 0


@dataclass
class Shared:
    sent: dict[str, tuple[str, float]] = field(default_factory=dict)  # event key -> (workspace, send time)
    acked: dict[str, float] = field(default_factory=dict)  # event key -> acknowledgement time
    acked_objects: dict[str, list[str]] = field(default_factory=dict)  # workspace -> board object ids
    list_latency: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    window_open: asyncio.Event = field(default_factory=asyncio.Event)


def report_passes(report: dict, *, enforce_targets: bool) -> bool:
    """Integrity, completeness and isolation gate every rehearsal; latency targets only when enforced."""
    integrity = (
        report["workload"]["clients_subscribed"] == report["workload"]["clients"]
        and report["workload"]["clients"] >= 2
        and report["workload"]["workspaces"] == 2
        and report["board_ops_acknowledged"] > 0
        and report["chat_messages_acknowledged"] > 0
        and report["deliveries_expected"] > 0
        and report["deliveries_missing"] == 0
        and report["isolation_violations"] == 0
        and report["lost"] == 0
        and report["duplicates"] == 0
        and not report["revision_gaps"]
        and report["error_count"] == 0
    )
    return integrity and (not enforce_targets or all(report["targets"].values()))


def ssl_context(cafile: str | None) -> ssl.SSLContext | None:
    return ssl.create_default_context(cafile=cafile) if cafile else None


async def activate(http: dict, api: str, activation: dict, *, wait_s: float = 15, max_wait_s: float = 900) -> None:
    """Activate one account, waiting out the server's per-client activation rate limit (never bypassing it)."""
    waited = 0.0
    while True:
        async with httpx.AsyncClient(**http) as fresh:
            r = await fresh.post(f"{api}/auth/activate", json=activation)
        if r.status_code != 429:
            r.raise_for_status()
            return
        if waited >= max_wait_s:
            r.raise_for_status()
        print(f"activation rate limited; waiting {wait_s:.0f} s", flush=True)
        await asyncio.sleep(wait_s)
        waited += wait_s


async def provision(http: dict, api: str, clients: int, drawers: int, workspace_names: list[str]) -> list[Client]:
    async with httpx.AsyncClient(**http) as admin:
        h = {"X-CSRF-Token": await login(admin, api, "admin", PASSWORD)}
        spaces = (await admin.get(f"{api}/admin/workspaces")).json()["workspaces"]
        ids = [next(w["id"] for w in spaces if w["name"] == name) for name in workspace_names]
        tag = secrets.token_hex(3)
        result = []
        for i in range(clients):
            username = f"rh{tag}{i:02d}"
            r = await admin.post(f"{api}/admin/users", json={"username": username, "display_name": f"Rehearsal {i}"},
                                 headers=h)
            r.raise_for_status()
            activation = {"token": r.json()["activation_token"], "password": PASSWORD}
            await activate(http, api, activation)
            workspace = ids[i % len(ids)]  # alternate, so drawers and readers are split across workspaces
            membership = {"user_id": r.json()["user"]["id"]}
            (await admin.put(f"{api}/admin/workspaces/{workspace}/memberships", json=membership,
                             headers=h)).raise_for_status()
            result.append(Client(username, workspace, drawer=i < drawers))
        return result


async def listen(client: Client, origin: str, base: str, cookie: str, ctx: ssl.SSLContext | None,
                 stop: asyncio.Event, ready: asyncio.Event) -> None:
    url = origin.replace("http", "ws", 1) + f"{base}/ws/"
    async with websockets.connect(url, additional_headers={"Cookie": cookie}, origin=origin, ssl=ctx,
                                  max_size=2**20) as sock:
        await sock.send(json.dumps({"type": "subscribe", "workspace_id": client.workspace}))
        while not stop.is_set():
            try:
                msg = json.loads(await asyncio.wait_for(sock.recv(), timeout=0.5))
            except asyncio.TimeoutError:
                continue
            now = time.perf_counter()
            kind = msg.get("type")
            if kind == "subscribed":
                client.subscribed_at = now
                ready.set()
                continue
            if kind == "board.op":
                workspace, key = msg["workspace_id"], "op:" + msg["op"]["op_id"]
            elif kind == "chat.message":
                workspace, key = msg["message"]["workspace_id"], "chat:" + msg["message"]["client_id"]
            else:
                continue
            if workspace != client.workspace:
                client.foreign_events += 1
            client.received.setdefault(key, now)


async def run_client(client: Client, http: dict, api: str, origin: str, base: str, ctx, epochs: dict, until: float,
                     interval: float, shared: Shared, stop: asyncio.Event) -> None:
    async with httpx.AsyncClient(timeout=15, **http) as c:
        h = {"X-CSRF-Token": await login(c, api, client.username, PASSWORD)}
        cookie = "; ".join(f"{k}={v}" for k, v in c.cookies.items())
        ready = asyncio.Event()
        socket = asyncio.create_task(listen(client, origin, base, cookie, ctx, stop, ready))
        await asyncio.wait_for(ready.wait(), 20)
        await shared.window_open.wait()
        i = 0
        while time.perf_counter() < until:
            if client.drawer:
                op_id = f"{client.username}-{i:05d}"
                x, y = random.uniform(0, 1500), random.uniform(0, 900)
                points = [[round(x + k * 4, 1), round(y + random.uniform(-3, 3), 1)] for k in range(40)]
                body = {"op_id": op_id, "epoch": epochs[client.workspace], "type": "add", "object_id": f"o-{op_id}",
                        "payload": {"kind": "stroke", "data": {"points": points, "color": "#1565c0", "width": 3}}}
                key = "op:" + op_id
                shared.sent[key] = (client.workspace, time.perf_counter())
                r = await c.post(f"{api}/workspaces/{client.workspace}/board/ops", json=body, headers=h)
                if r.status_code == 200:
                    shared.acked[key] = time.perf_counter()
                    shared.acked_objects.setdefault(client.workspace, []).append(body["object_id"])
                else:
                    shared.errors.append(f"board {r.status_code} {r.text[:100]}")
                pause = interval
            else:
                action = i % 4
                if action == 3:  # chat message: delivered live to every client of this workspace
                    client_id = f"{client.username}-c{i:05d}"
                    key = "chat:" + client_id
                    shared.sent[key] = (client.workspace, time.perf_counter())
                    r = await c.post(f"{api}/workspaces/{client.workspace}/chat",
                                     json={"body": f"rehearsal message {i}", "client_id": client_id}, headers=h)
                    if r.status_code == 201:
                        shared.acked[key] = time.perf_counter()
                    else:
                        shared.errors.append(f"chat {r.status_code} {r.text[:100]}")
                else:  # ordinary list views: feed, chat history, workspace list
                    path = (f"/workspaces/{client.workspace}/posts", f"/workspaces/{client.workspace}/chat",
                            "/workspaces")[action]
                    t0 = time.perf_counter()
                    r = await c.get(api + path)
                    if r.status_code == 200:
                        shared.list_latency.append((time.perf_counter() - t0) * 1000)
                    else:
                        shared.errors.append(f"list {r.status_code}")
                pause = random.uniform(2.0, 6.0)  # people read between actions
            i += 1
            await asyncio.sleep(pause)
        await stop.wait()  # keep listening until in-flight fanout has drained
        await socket


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--synthetic-target", action="store_true", required=True,
                    help="Attest this is a disposable synthetic development/test instance, never production")
    ap.add_argument("--origin", default="http://127.0.0.1:8080")
    ap.add_argument("--base", default="")
    ap.add_argument("--cafile", help="CA bundle for an https origin (e.g. the local rehearsal CA)")
    ap.add_argument("--clients", type=int, default=30)
    ap.add_argument("--drawers", type=int, default=8)
    ap.add_argument("--seconds", type=float, default=900)
    ap.add_argument("--interval", type=float, default=0.5, help="pause between strokes per drawer")
    ap.add_argument("--workspaces", default=",".join(DEFAULT_WORKSPACES))
    ap.add_argument("--out")
    ap.add_argument("--enforce-targets", action="store_true")
    args = ap.parse_args()
    names = [n.strip() for n in args.workspaces.split(",") if n.strip()]
    if not (1 <= args.drawers < args.clients and args.seconds > 0 and len(names) == 2):
        ap.error("need 1 <= drawers < clients, positive seconds and exactly two workspaces")
    ctx = ssl_context(args.cafile)
    http = {"base_url": args.origin, "verify": ctx if ctx else True}
    api = f"{args.base}/api/v1"
    clients = await provision(http, api, args.clients, args.drawers, names)
    workspaces = sorted({c.workspace for c in clients})
    # Board integrity is read back by a rehearsal member of each workspace (admins have no content grant).
    verifier = {w: next(c.username for c in clients if c.workspace == w) for w in workspaces}
    starts, epochs = {}, {}
    for w in workspaces:
        async with httpx.AsyncClient(**http) as c:
            await login(c, api, verifier[w], PASSWORD)
            starts[w] = (await c.get(f"{api}/workspaces/{w}/board")).json()
            epochs[w] = starts[w]["epoch"]
    shared, stop = Shared(), asyncio.Event()
    started = time.perf_counter()
    until = started + args.seconds + 20  # sockets get up to 20 s to subscribe before the window opens
    tasks = [asyncio.create_task(run_client(c, http, api, args.origin, args.base, ctx, epochs, until,
                                            args.interval, shared, stop)) for c in clients]
    while sum(c.subscribed_at is not None for c in clients) < len(clients) and time.perf_counter() < started + 20:
        await asyncio.sleep(0.2)
    window_start = time.perf_counter()
    shared.window_open.set()
    await asyncio.sleep(max(0.0, until - time.perf_counter()))
    await asyncio.sleep(5)  # drain in-flight fanout
    stop.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            shared.errors.append(f"client {type(r).__name__}: {str(r)[:100]}")

    # Board integrity per workspace (including compaction during the run).
    lost = duplicates = 0
    gaps = False
    retained = {}
    for w in workspaces:
        async with httpx.AsyncClient(**http) as c:
            await login(c, api, verifier[w], PASSWORD)
            final = (await c.get(f"{api}/workspaces/{w}/board",
                                 params={"epoch": epochs[w], "after": starts[w]["revision"]})).json()
        revisions = [o["revision"] for o in final["ops"]]
        floor = max(starts[w]["revision"], final.get("base_revision", 0)) if final["reset"] else starts[w]["revision"]
        gaps = gaps or revisions != list(range(floor + 1, floor + 1 + len(revisions)))
        present = set((final.get("snapshot") or {}).get("objects", {})) | {o["object_id"] for o in final["ops"]}
        objects = shared.acked_objects.get(w, [])
        lost += sum(1 for o in objects if o not in present)
        duplicates += len(revisions) - len(set(revisions)) + len(objects) - len(set(objects))
        retained[w] = {"ops_retained": len(revisions), "compacted_through": final.get("base_revision", 0)}

    # Delivery completeness and latency over every (event, receiving client) pair.
    expected = missing = 0
    latency: list[float] = []
    for key in shared.acked:
        workspace, sent_at = shared.sent[key]
        for client in clients:
            if client.workspace != workspace or client.subscribed_at is None or client.subscribed_at > sent_at:
                continue
            expected += 1
            arrived = client.received.get(key)
            if arrived is None:
                missing += 1
            else:
                latency.append((arrived - sent_at) * 1000)
    board_ops = sum(k.startswith("op:") for k in shared.acked)
    chats = sum(k.startswith("chat:") for k in shared.acked)
    report = {
        "environment": {"python": platform.python_version(), "system": platform.system(),
                        "machine": platform.machine(), "logical_cpus": os.cpu_count(),
                        "tls": args.origin.startswith("https://"), "origin": args.origin, "base": args.base},
        "workload": {"clients": args.clients, "drawers": args.drawers, "readers": args.clients - args.drawers,
                     "workspaces": len(workspaces), "seconds": args.seconds, "drawer_interval_s": args.interval,
                     "clients_subscribed": sum(c.subscribed_at is not None for c in clients)},
        "elapsed_seconds": round(time.perf_counter() - window_start, 2),
        "board_ops_acknowledged": board_ops, "chat_messages_acknowledged": chats,
        "deliveries_expected": expected, "deliveries_missing": missing,
        "isolation_violations": sum(c.foreign_events for c in clients),
        "lost": lost, "duplicates": duplicates, "revision_gaps": gaps, "boards": retained,
        "errors": shared.errors[:10], "error_count": len(shared.errors),
        "latency_samples": len(latency), "list_samples": len(shared.list_latency),
        "update_latency_ms": {"p50": metric(latency, 50), "p95": metric(latency, 95),
                              "max": round(max(latency), 1) if latency else None,
                              "mean": round(statistics.mean(latency), 1) if latency else None},
        "list_latency_ms": {"p50": metric(shared.list_latency, 50), "p95": metric(shared.list_latency, 95)},
        "targets": {"update_p95_lt_500ms": bool(latency) and pct(latency, 95) < 500,
                    "list_p95_lt_1000ms": bool(shared.list_latency) and pct(shared.list_latency, 95) < 1000},
    }
    report["passed"] = report_passes(report, enforce_targets=args.enforce_targets)
    report["targets_enforced"] = args.enforce_targets
    text = json.dumps(report, indent=2, allow_nan=False)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
