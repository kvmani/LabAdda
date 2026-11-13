# Earlier handoff entries

Moved from ROADMAP.md when the private-board work was recorded.

| Date · package · status | What changed and evidence | Assumptions, limits, questions | Next action |
| --- | --- | --- | --- |
| 2026-11-12 · P4 · delivered, independent review pending | Organisation chart page (`features/org/`: SVG chart, zoom, fit, collapse, search, keyboard path, side panel, drag to Transfer or Move review), seven unit kinds on the change protocol (create, rename, move, merge, split, close, reopen), `workspaces.code` (migration 0034), `GET /admin/org/tree` (names, roles, counts only), three help pages, `e2e/org-chart.mjs`. Evidence (worker): `scripts/verify.sh` OK (vitest 203); org-chart 42 checks, people, people-changes and people-authority green at root and prefix. | Not done: the old basic admin screens and `/admin/users`, `/admin/workspaces` endpoints stay (over 20 test files and 16 suites use them; the basic page is the only project-creation screen, now linked as "Basic project tools"). `e2e/admin-console.mjs` reported failing at its overview check. Merge gives moved people plain member role; members keep read access to the archived source. | Independent review; fix admin-console suite; P5. |
