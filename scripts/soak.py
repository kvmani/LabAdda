#!/usr/bin/env python3
"""Board drawing soak against a running test instance (P3 item 5, P4 rehearsal prep).

Creates N synthetic drawer accounts through the admin API, has them draw on one
board while an observer socket measures local-to-remote committed-update latency,
then checks for lost, duplicated or out-of-order revisions. Development/test
instances only: it signs in with the fixture admin and adds accounts.

    .venv/bin/python scripts/soak.py --origin http://127.0.0.1:8080 --drawers 8 --seconds 60
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import secrets
import statistics
import time

import httpx
import websockets

PASSWORD = os.environ.get("LABADDA_FIXTURE_PASSWORD", "fixture-pass-123")


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


def report_passes(report: dict, *, enforce_targets: bool) -> bool:
    """Zero samples or partial socket delivery cannot qualify a rehearsal."""
    integrity = (
        report["ops_acknowledged"] > 0
        and report["ops_seen_by_observer"] == report["ops_acknowledged"]
        and not report["lost"]
        and not report["duplicates"]
        and not report["revision_gaps"]
        and report["error_count"] == 0
    )
    return integrity and (not enforce_targets or all(report["targets"].values()))


def metric(values: list[float], percentile: float) -> float | None:
    return round(pct(values, percentile), 1) if values else None


async def login(client: httpx.AsyncClient, api: str, username: str, password: str) -> str:
    r = await client.post(f"{api}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["csrf_token"]


async def make_drawers(origin: str, api: str, n: int, workspace_name: str) -> tuple[str, list[str]]:
    async with httpx.AsyncClient(base_url=origin) as admin:
        csrf = await login(admin, api, "admin", PASSWORD)
        h = {"X-CSRF-Token": csrf}
        spaces = (await admin.get(f"{api}/admin/workspaces")).json()["workspaces"]
        ws_id = next(w["id"] for w in spaces if w["name"] == workspace_name)
        tag = secrets.token_hex(3)
        names = []
        for i in range(n):
            username = f"soak{tag}{i:02d}"
            r = await admin.post(
                f"{api}/admin/users", json={"username": username, "display_name": f"Soak {i}"}, headers=h
            )
            r.raise_for_status()
            token = r.json()["activation_token"]
            async with httpx.AsyncClient(base_url=origin) as fresh:
                (
                    await fresh.post(f"{api}/auth/activate", json={"token": token, "password": PASSWORD})
                ).raise_for_status()
            (
                await admin.put(
                    f"{api}/admin/workspaces/{ws_id}/memberships",
                    json={"user_id": r.json()["user"]["id"]},
                    headers=h,
                )
            ).raise_for_status()
            names.append(username)
        return ws_id, names


async def observer(
    origin: str, base: str, api: str, ws_id: str, seen: dict, ready: asyncio.Event, stop: asyncio.Event
):
    async with httpx.AsyncClient(base_url=origin) as c:
        await login(c, api, "asha", PASSWORD)
        cookie = "; ".join(f"{k}={v}" for k, v in c.cookies.items())
    url = origin.replace("http", "ws", 1) + f"{base}/ws/"
    async with websockets.connect(
        url, additional_headers={"Cookie": cookie}, origin=origin, max_size=2**20
    ) as sock:
        await sock.send(json.dumps({"type": "subscribe", "workspace_id": ws_id}))
        while not stop.is_set():
            try:
                msg = json.loads(await asyncio.wait_for(sock.recv(), timeout=0.5))
            except TimeoutError:
                continue
            if msg["type"] == "subscribed":
                ready.set()
            elif msg["type"] == "board.op":
                seen.setdefault(msg["op"]["op_id"], time.perf_counter())


async def drawer(
    origin: str,
    api: str,
    ws_id: str,
    username: str,
    epoch: int,
    until: float,
    interval: float,
    sent: dict,
    acks: list,
    acked_objects: list,
    errors: list,
    list_latency: list,
):
    async with httpx.AsyncClient(base_url=origin, timeout=10) as c:
        csrf = await login(c, api, username, PASSWORD)
        h = {"X-CSRF-Token": csrf}
        i = 0
        while time.perf_counter() < until:
            op_id = f"{username}-{i:05d}"
            x, y = random.uniform(0, 1500), random.uniform(0, 900)
            pts = [[round(x + k * 4, 1), round(y + random.uniform(-3, 3), 1)] for k in range(40)]
            body = {
                "op_id": op_id,
                "epoch": epoch,
                "type": "add",
                "object_id": f"o-{op_id}",
                "payload": {"kind": "stroke", "data": {"points": pts, "color": "#1565c0", "width": 3}},
            }
            sent[op_id] = time.perf_counter()
            r = await c.post(f"{api}/workspaces/{ws_id}/board/ops", json=body, headers=h)
            if r.status_code == 200:
                revision = r.json()["committed"]["revision"]
                acks.append(revision)
                acked_objects.append(body["object_id"])
                if i % 10 == 0:  # retry with the same op_id: must return the same revision
                    again = await c.post(f"{api}/workspaces/{ws_id}/board/ops", json=body, headers=h)
                    if again.json().get("committed", {}).get("revision") != revision:
                        errors.append(f"retry mismatch {op_id}")
            else:
                errors.append(f"{r.status_code} {r.text[:120]}")
            if i % 5 == 0:
                t0 = time.perf_counter()
                (await c.get(f"{api}/workspaces/{ws_id}/posts")).raise_for_status()
                list_latency.append((time.perf_counter() - t0) * 1000)
            i += 1
            await asyncio.sleep(interval)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="http://127.0.0.1:8080")
    ap.add_argument("--base", default="")
    ap.add_argument("--drawers", type=int, default=8)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--interval", type=float, default=0.25, help="pause between strokes per drawer")
    ap.add_argument("--workspace", default="Thin Films Section")
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--enforce-targets", action="store_true", help="fail when update/list p95 exceeds S4 targets"
    )
    args = ap.parse_args()
    if args.drawers < 1 or args.seconds <= 0 or args.interval < 0:
        ap.error("drawers and seconds must be positive; interval must be nonnegative")
    api = f"{args.base}/api/v1"
    ws_id, names = await make_drawers(args.origin, api, args.drawers, args.workspace)
    async with httpx.AsyncClient(base_url=args.origin) as c:
        await login(c, api, "asha", PASSWORD)
        start_state = (await c.get(f"{api}/workspaces/{ws_id}/board")).json()
    seen, sent, acks, acked_objects, errors, list_latency = {}, {}, [], [], [], []
    ready, stop = asyncio.Event(), asyncio.Event()
    obs = asyncio.create_task(observer(args.origin, args.base, api, ws_id, seen, ready, stop))
    await asyncio.wait_for(ready.wait(), 10)
    started = time.perf_counter()
    until = started + args.seconds
    await asyncio.gather(
        *(
            drawer(
                args.origin,
                api,
                ws_id,
                n,
                start_state["epoch"],
                until,
                args.interval,
                sent,
                acks,
                acked_objects,
                errors,
                list_latency,
            )
            for n in names
        )
    )
    await asyncio.sleep(2)
    stop.set()
    await obs
    async with httpx.AsyncClient(base_url=args.origin) as c:
        await login(c, api, "asha", PASSWORD)
        final = (
            await c.get(
                f"{api}/workspaces/{ws_id}/board",
                params={"epoch": start_state["epoch"], "after": start_state["revision"]},
            )
        ).json()
    # Every acknowledged stroke must exist exactly once, in the compacted snapshot or in retained ops.
    revisions = [o["revision"] for o in final["ops"]]
    floor = (
        max(start_state["revision"], final.get("base_revision", 0))
        if final["reset"]
        else start_state["revision"]
    )
    expected = list(range(floor + 1, floor + 1 + len(revisions)))
    present = set((final.get("snapshot") or {}).get("objects", {})) | {o["object_id"] for o in final["ops"]}
    missing = [r for r in acked_objects if r not in present]
    latency = [(seen[k] - sent[k]) * 1000 for k in sent if k in seen]
    report = {
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "tls": args.origin.startswith("https://"),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "latency_samples": len(latency),
        "list_samples": len(list_latency),
        "drawers": args.drawers,
        "seconds": args.seconds,
        "interval_s": args.interval,
        "ops_acknowledged": len(acks),
        "ops_retained": len(revisions),
        "compacted_through": final.get("base_revision", 0),
        "ops_seen_by_observer": len(latency),
        "lost": len(missing),
        "duplicates": len(revisions) - len(set(revisions)) + len(acked_objects) - len(set(acked_objects)),
        "revision_gaps": revisions != expected,
        "errors": errors[:10],
        "error_count": len(errors),
        "update_latency_ms": {
            "p50": metric(latency, 50),
            "p95": metric(latency, 95),
            "max": round(max(latency), 1) if latency else None,
            "mean": round(statistics.mean(latency), 1) if latency else None,
        },
        "list_latency_ms": {"p50": metric(list_latency, 50), "p95": metric(list_latency, 95)},
        "targets": {
            "update_p95_lt_500ms": bool(latency) and pct(latency, 95) < 500,
            "list_p95_lt_1000ms": bool(list_latency) and pct(list_latency, 95) < 1000,
        },
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
