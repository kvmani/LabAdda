# LabAdda review plan

Review the candidate commit against the relevant specification sections and test IDs. Use an independent reviewer for the authorization, realtime, and deployment milestones. Review changes in a disposable environment with synthetic data. Compare the candidate to its actual base and reproduce the highest-impact failure paths.

1. Trace one real workflow from browser to API or socket, policy, transaction, and visible result. Inspect what happens when a request is denied, retried, interrupted, or sent concurrently.
2. Try the same action with a sibling user, parent-only user, invited project member, administrator without content access, stale membership, and board-only session as applicable. Include downloads, thumbnails, counts, search, notification delivery, and reconnect. The relevant invariants and tests are in [SPECIFICATIONS.md](SPECIFICATIONS.md) and [TESTING.md](TESTING.md).
3. Check migrations, replay and idempotency, backup consistency, release rollback claims, and offline dependencies. Inspect logs and artifacts for real data and private topology. Review the deployment design before approving an operational change.
4. Check the interface in a browser. Look for ambiguous posting scope, weak failure feedback, lost draft state, unreadable controls, and board-only sessions that expose personal information. Record physical panel evidence separately.
5. Report findings by severity. Include a path and line or test ID, impact, reproduction steps, and the smallest defensible correction. Track each finding as open, fixed with evidence, or accepted by the owner with a reason. Verify fixes at the updated commit.

| Severity | Examples | Gate |
| --- | --- | --- |
| Blocker | Cross-workspace or personal-data leak, durable edit loss, unusable restore, external runtime dependency, exposed credentials | Stop release and verify the fix |
| High | Broken sign-in, incorrect audience on publish, stale session retaining access, mandatory pilot flow unavailable | Fix and retest before pilot |
| Medium or low | Contained usability issue or minor maintainability defect | Record disposition and follow-up |

End with the candidate SHA, scope reviewed, evidence and gaps, and a decision of **ready for next milestone**, **ready for supervised pilot**, or **changes required**. Synthetic evidence supports engineering readiness. The site owner decides pilot activation after the site gates pass.
