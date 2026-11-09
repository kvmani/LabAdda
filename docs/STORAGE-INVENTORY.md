# Asset-directory inventory (P5.1 observation only)

Run `labadda inventory-storage --max-entries 10000 --max-assets 10000 --max-seconds 30`
from the trusted host with the configured database and asset directory. This reads
metadata only and records a durable `storage_inspections` receipt plus audit event.
It never changes files, repairs accounting, or authorizes deletion. Exit 0 means
the bounded directory pass finished without reported issues; exit 2 means partial,
failed or unconfirmed. A killed process can leave a running receipt: do not infer
success or blindly retry a destructive operation from it.

The command first selects at most `max-assets + 1` database asset references. If
they exceed the bound, it stops before classification. It then enumerates the root
and the store's two-character shard directories using directory descriptors and
no-follow opens. Every directory entry consumes the entry budget. Symlinks,
special files, changed directories, nested/unexpected directories and other
filesystems are not traversed. Failures remain visible as sanitized counts. Limits
are 100,000 entries/references and 300 seconds; time is cooperative, including no
hard guarantee against a stalled filesystem operation. Database selection has a
two-second statement timeout. There is no resumable cursor yet; a larger site
requires a later paginated generation protocol.

`apparent_bytes` sums file lengths once per observed device/inode pair;
`allocated_bytes` sums their reported disk blocks (512-byte units). Neither is a
complete filesystem-usage meter: directory metadata, external hard links, shared
extents, snapshots and unrelated services are outside the observation. Per-class
counts and lengths count directory entries, so hard-link aliases can make class
sums exceed physical totals. No bytes are read or hashes verified.

Classes are referenced originals, referenced previews, temporary files,
unreferenced candidates and unexpected files. An unreferenced candidate means
only that its storage key was absent from the earlier reference selection (or a
preview was not expected). It may belong to an in-flight/uncertain upload. Never
remove it based on this receipt. Live filesystem/database changes are possible;
receipts always carry `complete_for_enforcement: false` and
`deletion_authorized: false`. Missing referenced files require the separate
`labadda inspect-storage` command. No filenames, storage keys, paths, content or
owner identities appear in inventory receipts.

Inspect aggregate receipts using the existing authorized administration API
`GET /admin/storage-inspections`. The admin governance view presents these receipts with aggregate class totals,
allocation caveats and actionable scan/issue guidance. It offers no web scan or
cleanup action.
