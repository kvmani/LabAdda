# Current collaboration screenshot review

Captured on 2026-11-10 against the preserved synthetic research demo at schema 0020. These are running-app screenshots, not mockups. See the [research-day scenario](../../../fixtures/research-day/README.md) for the five identities, two sibling sections and shared division.

## Reproduce

After preparing the research-day scenario and the current frontend/migrations, run with Playwright available:

```bash
node e2e/collaboration-review.mjs http://127.0.0.1:8010 /tmp/collaboration-review --synthetic-instance
```

The runner refuses non-local origins and requires the explicit synthetic flag. It adds review fixtures through authenticated APIs, reuses named records and stable board/chat operation identifiers, and never resets data or grants. Use a dedicated synthetic instance. Existing edited review records are preserved; this is a review capture, not a fixture reset or general acceptance suite. `LABADDA_CHROMIUM` and `LABADDA_FIXTURE_PASSWORD` override local defaults.

## Evidence and limits

Twelve PNGs, a self-contained HTML gallery and JSON check report cover five separately authenticated whiteboard views, shared chat, five assigned tasks with dates/priorities/checklists/states, five-author task discussion, personal lists, My Tasks, My Notes and handwritten private stickies. Existing native research-plan strokes are preserved; all five participants contribute a new ink mark and appear in board presence.

The private stickies use an owner-only group board, **not a dedicated personal-whiteboard feature**. The runner verifies that all four colleagues receive 404 for the owner's note, personal tasks and scratchpad. Whiteboard/chat use existing live delivery; task/comment changes require refresh. No notification or live-task capability is claimed. The capture passed all five reported checks with no browser errors or external asset requests. No product code was changed.

The dated review artifacts are delivered separately as `collaboration-review-2026-11-10.zip` (12 PNGs, gallery and report). Screenshots are human review evidence, not pixel-golden tests. Existing authorization, recovery and collaboration suites remain authoritative.
