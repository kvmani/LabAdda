# Preview reconciliation receipts

- [Root dry-run receipt](dry-run-root.png)
- [Prefixed dry-run receipt](dry-run-prefix.png)

Captured by `e2e/preview-reconciliation-view.mjs` after actual host-operator CLI dry runs on disposable proxy-stack fixtures. These fixtures contain newly recorded previews, so zero unknown candidates and zero updates are expected. The view distinguishes dry runs from normal file verification and offers no web application action.

Nonzero dry-run/application, changed-plan refusal and failure/rollback behavior are exercised against synthetic PostgreSQL state in `test_preview_reconciliation.py`. No real site metadata was backfilled and no stored bytes were changed for this evidence.
