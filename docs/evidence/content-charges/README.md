# Text and whiteboard logical charges

Captured by `e2e/content-charges.mjs` on a fresh disposable `scripts/proxy-stack.sh` stack, at root and `/labadda-staging`:

- [User usage, root](root-user-usage.png) and [prefix](labadda-staging-user-usage.png). A 16-character post is charged as its 26 UTF-8 bytes, and a drawn stroke is charged to its author.
- [Admin view with an unreconciled historical board, root](root-admin-incomplete.png) and [prefix](labadda-staging-admin-incomplete.png). Board totals are labeled a lower bound, not zero.
- [Admin view after a real operator dry run and reviewed apply, root](root-admin-reconciled.png) and [prefix](labadda-staging-admin-reconciled.png). Both receipts are listed, and the lower-bound notice is gone.

The "historical" board is simulated by clearing its board-object ledger rows and coverage marker in the disposable e2e database. The apply step ran without concurrent writers on the test stack; `--writers-quiesced` is an operator attestation, not something the tool verifies. No real-site data was reconciled.
