# Metrics foundation

Read [A3](../plan/admin.md#a3--metrics-foundation), [AD-05 and AD-08](../ADMIN-CONSOLE-V1.md)
and [API A3](../API.md#a3--metrics-foundation-ad-08-schema-0027). Tests: T61, T62.

## Where things are

| Module | Job |
| --- | --- |
| `metrics/catalog.py` | The fixed list: name, kind, unit, allowed dimension values, route groups |
| `metrics/registry.py` | Thread-safe per-minute counters, gauges, fixed-bucket latency histograms |
| `metrics/counters.py` | `count`, `count_workspace`, `count_attachments` and their `*_on_commit` forms |
| `metrics/middleware.py` | Pure ASGI: requests, 5xx errors and latency by route group |
| `metrics/gauges.py` | Sessions seen in 5 minutes, sockets, database, asset and free disk bytes |
| `metrics/activity.py` | One `activity_days` row per person per site-local day |
| `metrics/flush.py` | One batched upsert of closed minutes |
| `metrics/rollup.py` | Minutes → site-local hours → site-local days; retention |
| `metrics/collector.py` | The scheduler job tying gauges, flush and roll-up together |
| `api/metrics.py` | `GET /admin/metrics/series` |

Tables (migration 0027): `metric_samples` (primary key bucket, resolution, metric, dimension)
and `activity_days` (user, day). The downgrade refuses while either holds rows; older
downgrade tests clear synthetic rows through `tests/migration_helpers.downgrade_legacy`.

## Rules for adding a count

- Add the metric to `catalog.py` first (at most 60 metrics, 40 values per metric). Unknown
  names and dimension values raise; this is the cardinality guard.
- Count only committed work. In a router, call `metrics.count_workspace(...)` right after
  `db.commit()` on the path that created something, never on the "already exists" path of an
  idempotent retry. In shared helpers, or where the commit may end in an unknown outcome, use
  `count_workspace_on_commit(db, ...)`: the session's outermost commit applies it and a
  rollback drops it (savepoint releases do not count).
- Feature counters use the unit kind (`org`, `project`, `group`) and, for `org`, also
  `unit:<id>`. Sum the three kinds for a total; never add the unit values to them. Units
  beyond the per-metric budget fold into `unit:other`.
- Never count personal notes, personal task lists or board-only panel sessions. Note
  reminders and personal-list tasks are skipped in `notify.py` and `api/todos.py`.
- Dimensions never hold content, user text, paths, IDs other than organisation units, or
  query strings. Route groups come from the route template (`route_group`).

## What is counted where

| Metric | Commit point |
| --- | --- |
| `posts.created` | `api/posts.create_post`; board snapshot publish (on commit) |
| `replies.created` | `api/posts.reply` |
| `chat.messages` | `api/chat.send` |
| `board.operations` | `api/board.submit_op` (duplicates excluded) |
| `tasks.created`, `tasks.completed` | `api/todos._create_task_row`, `edit_task` (workspace lists) |
| `uploads.count`, `uploads.bytes` | When a file is attached to a post, chat message or board |
| `notifications.created` | `notify.create` (workspace notifications, on commit) |
| `auth.signin_ok`, `auth.signin_failed` | `api/auth.login` |

Uploads count when a file gets a destination: a provisional upload has no workspace yet, and
note attachments do not exist. `tasks.completed` counts a task created done or changed to done.

## Collection and storage

- The registry keys every value by its UTC minute, read under its lock, so a value can never
  land in a minute a concurrent flush already treated as closed.
- `Collector.tick` runs on every scheduler tick but works once per
  `LABADDA_METRICS_FLUSH_SECONDS`: it samples gauges into the current minute, then writes
  every closed minute in one upsert. Rows hold absolute minute totals and the upsert replaces
  them, so a flush repeated after a failure between commit and `discard` stores the same
  numbers. A restart loses the open minute; that shows as a gap.
- A gauge that cannot be read (for example the asset volume is missing) is skipped, so it is
  unknown, never zero. Gauge queries run with a 2 s statement timeout.
- Roll-up runs once per site-local hour. It recomputes whole buckets (the newest existing one
  again, then every complete bucket after it) and replaces them, so it is idempotent and catches
  up after downtime. Hours are site-local so that a +05:30 zone still nests hours inside days.
  Counters sum, gauges keep the maximum (peaks), percentiles take the request-weighted mean of
  their parts — an approximation, because exact percentiles cannot be merged.
- Retention: minutes 48 hours, hours 35 days, days 2 years, activity days 2 years (settings
  `LABADDA_METRICS_*_RETENTION_*`, `LABADDA_ACTIVITY_RETENTION_DAYS`).
- The scheduler runs each job in its own error boundary; a metrics failure is logged as
  `scheduler.job_failed` and never stops reminders or file cleanup.

## Activity days

`deps._load_actor` calls `ACTIVITY.record` for normal sessions only. A process-wide "seen
today" set means only the first signed-in request of a site-local day writes (insert, ignoring
duplicates); it is cleared when the site day changes. It records no pages, actions or times.

## Assumptions to keep in mind

- One server process (the systemd service runs one uvicorn worker). Minute rows are absolute
  per process; several workers would overwrite each other's minutes.
- Series do not expose per-unit values; A5 adds summaries with small-group protection.
- The S4 load rehearsal with metrics on is recorded by the coordinator (see the A3 card).
