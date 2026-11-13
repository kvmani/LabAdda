# Five-person research-day regression scenario

Everything here is synthetic, including the scientific claims and handoff measurements. This opt-in scenario extends a dedicated copy of the standard fictional fixture; it does not change the default seed, existing development database or test database.

| Person | Normal workspace | Scenario contribution |
| --- | --- | --- |
| Asha Rao (`asha`) | Thin Films Section, steward | Film preparation, controls, yellow sticky |
| Bharat Kulkarni (`bharat`) | Thin Films Section | Sample/run mapping, blue sticky, private handoff |
| Chitra Iyer (`chitra`) | Corrosion Section | GC replicates, orange sticky, handoff recipient |
| Mira Sen (`mira`, scenario-only account) | Corrosion Section | XPS surface checks, green sticky |
| Deepa Nair (`deepa`) | Surface Engineering Division, steward | Decision gate, division notice, yellow sticky |

All five join **Tejas - coating trials**, an explicitly chosen cross-section group with its own board/chat/feed. The division remains their shared hierarchy scope. Neither sibling section gains access to the other; Deepa's division stewardship does not flow downward into either section. Bharat and Chitra also use a separate two-person group for an attached preliminary PDF. This original capture predates C4 chat attachments: its private exchange uses group noticeboard attachments and group chat. Current C4 also supports validated chat/reply attachments and a private-group conversation shortcut; see [chat help page](../../frontend/src/help/using/chat-and-threads.md). Bharat's My Notes remains owner-only.

`scenario.json` provides the conversation, reviewed division notice and private handoff. `board-objects.json` provides **663 native objects**: five editable stickies and 658 pen strokes assigned to the five actors. The generator uses deterministic single-stroke lettering, so no downloaded fonts or external images are required. Sticky backgrounds precede ink to preserve painter order during concurrent replay. One additional stroke tests reconnect catch-up, giving revision 664 in the captured board.

SVG sources: [complete research plan](research-plan.svg), [schematic](interface-schematic.svg), [handwritten stickies](sticky-notes.svg). These are source test assets, not application-upload exceptions. Raw SVG, including SVG mislabeled as PNG, must be rejected. The browser harness renders a PNG reference and uploads that through the existing validated boundary. The live board itself uses native strokes/stickies, not that PNG.

## Reproduce

Install the normal locked dependencies, build the frontend and provision a **new disposable database** as described in README. Set the explicit synthetic URL in `LABADDA_DATABASE_URL` and keep `LABADDA_ENV=development` (or `test`). For example, with the same fictional local PostgreSQL credentials:

```bash
export LABADDA_DATABASE_URL=postgresql+psycopg://labadda:labadda-dev@localhost:5432/labadda_research_demo
export LABADDA_ENV=development
export LABADDA_ASSET_DIR="$PWD/var/research-assets"
.venv/bin/labadda migrate
.venv/bin/labadda seed
.venv/bin/labadda serve --port 8010
# In another terminal, with Playwright available:
node e2e/research-day.mjs http://127.0.0.1:8010 /tmp/research-day --synthetic-instance
```

The runner refuses non-local URLs, requires an explicit synthetic-instance flag, and refuses a previously populated scenario. It never resets a database. For a repeat, provision another dedicated empty database or deliberately reset only your own disposable scenario after stopping writers. Five isolated Playwright contexts sign in through the real UI; API calls accelerate population while maintaining real server authorization, commits and sockets. Activity is accelerated, so displayed timestamps are capture times, not a reconstructed historical day. Screenshots use Asia/Kolkata. `LABADDA_CHROMIUM` overrides the default provided `/usr/bin/chromium`; the runtime's `NODE_PATH` exposes Playwright without changing dependency locks.

The runner saves eleven screenshots, a standalone HTML gallery, check report, rendered PNG and valid synthetic PDF. See the [captured gallery](../../docs/evidence/research-day/index.html). The seeded app remains available in the dedicated demo database after capture.

## Regression coverage

`backend/tests/test_research_fixture.py` verifies byte-for-byte regeneration, all five authors, native board validation, sticky-before-ink ordering, self-contained SVG, and real-upload refusal of SVG under both SVG and forged PNG MIME types. The browser scenario verifies five authenticated sessions, operation retry deduplication, complete native persistence, five-author attribution, reconnect replay, group/private-file/note isolation, upward hierarchy access without downward/sibling leakage, authorized PDF delivery, and no browser errors/external requests. Screenshots are human review evidence, not time-sensitive pixel-golden assertions. Existing policy, socket, revocation, snapshot and recovery suites remain separate checks.

Regenerate source artwork with `python3 scripts/generate-research-art.py`; no application data is changed. Run focused tests with `.venv/bin/python -m pytest backend/tests/test_research_fixture.py` and the full suite with `LABADDA_RECOVERY_TESTS=1 scripts/verify.sh` when PostgreSQL clients/CREATEDB are available.

For fresh screenshots of current task assignments, discussions and private planning on the preserved scenario, use the [collaboration review capture guide](../../docs/evidence/collaboration-review/README.md).
