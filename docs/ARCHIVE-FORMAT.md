# Portable content archives — format and import contract

Status: **future specification, not an implemented format**. Normative companion to DL-19–DL-23. This format is for user content and must never be accepted as an operator PostgreSQL recovery bundle.

## Package layout and interoperability

**AF-01.** Use a standard ZIP package, extension `.labadda.zip`, with UTF-8 safe relative member names, regular files only, stored or DEFLATE compression, and no password-protected ZIP members. Export large selections as independent bounded packages rather than requiring ZIP64 in version 1. A site requiring encrypted off-device storage uses an approved external encryption/container process; the application must not invent cryptography or store an archive decryption secret alongside the package. Each part must remain inspectable with ordinary offline tools.

```text
manifest.json
checksums.sha256
index.html
styles.css
README.txt
records/workspaces.json
records/identities.json
records/posts.jsonl
records/chat.jsonl
records/notes.jsonl
boards/<archive-local-id>/state.json
boards/<archive-local-id>/replay.jsonl
boards/<archive-local-id>/preview.png
boards/<archive-local-id>/drawing.svg
files/<archive-local-id>.<approved-extension>
```

Empty record streams are permitted and explicitly listed. Only selected and authorized categories appear; a workspace export must not quietly acquire personal notes. Names in paths are generated archive-local identifiers, never raw original filenames or user-supplied directories. Original display names are escaped metadata. Text records are UTF-8, JSONL uses one valid JSON object per line, timestamps are RFC 3339 UTC, byte lengths are integers, and schema/format versions are explicit. Records retain ordering cursors, source revisions, parent relationships, durable content needed for reconstruction and provenance, not database engine rows. Export must not embed access cookies, password hashes, credential tokens, server filesystem paths, connection strings or hidden scope metadata.

**AF-02.** The manifest must include format name and major/minor version, archive UUID, export job ID, source instance public identifier (not private topology), creation time, stable snapshot cutoff, selection filters, included categories, record counts, dependency completeness, omitted/redacted categories with reasons, and every payload member's media type, byte length and SHA-256. Include package-set/part numbers when split, selected scope labels and identity attribution only as authorized at snapshot time, archive-local ID mappings, source content revisions, lifecycle/expiry/provenance labels, and minimum reader capabilities. An intentionally omitted file is different from corrupt/missing data. Never claim complete export if a dependency failed silently.

The manifest covers every payload file except itself and `checksums.sha256`. `checksums.sha256` covers the manifest and all payload files, excluding itself. Downloads also expose an external SHA-256 for the entire ZIP, covering both integrity indexes. This avoids circular checksums. Producers must validate their own output against AF-06 before completion; use stored members or split packages when normal content would exceed compression-ratio or package limits. Hashes prove byte integrity only; they do not authenticate who made an archive. Optional detached signatures must use an approved standard algorithm and independent trusted-key registry; unsigned archives remain viewable as untrusted data subject to all resource/renderer checks.

**AF-03.** A shipped, versioned JSON Schema and schema fixtures are required before this format is implemented. Readers must reject unsupported major versions or unknown required capabilities before materialization. Unknown optional fields may be preserved as inert metadata; do not execute extensions or silently downgrade semantics. A human-readable safe view may be offered for supported portions, clearly marked incomplete, while materialization remains disabled. Test at least the current and previous supported minor versions and a documented offline upgrade path. Archive-local IDs must never be treated as current server IDs.

## Human-readable offline view

**AF-04.** `index.html` and local CSS must open after ordinary extraction on a disconnected supported desktop browser. It must link readable transcripts, notes, board previews and authorized attachments using only package-relative paths. Use escaped static HTML, no JavaScript, external fonts, trackers, remote links that auto-fetch, service workers, inline event handlers or active embedded documents. Include visible source/cutoff, selection/omissions and synthetic-data labels when applicable. Provide a plain UTF-8 fallback and readable README explaining inspection, extraction and checksum verification using standard tools. Offline viewing must not depend on LabAdda, Node, Python, a database, a vendor cloud or an active account.

**AF-05.** Whiteboards include a renderer-independent PNG preview and native JSON state. Optional replay must declare the revision window, snapshot base and whether full history is intentionally unavailable. Controlled generated `drawing.svg` may contain only geometries/text from a strict renderer allowlist; no script, foreignObject, external resource, remote URL or untrusted raw SVG passthrough. Embed approved raster data only within package bounds or reference local assets through an explicitly tested offline strategy. The server's general SVG-upload refusal remains unchanged. Images shared with a broader audience must be copies the exporter can currently read, not protected links back to the original board.

## Verification and quarantine

**AF-06.** Before extraction/import, use a private snapshot of the uploaded bytes. Verify structure, supported version, complete manifest/checksum coverage, all member sizes/hashes, JSON record schemas and dependency graph. Fail on duplicate normalized names, absolute/drive/UNC paths, `..`, backslashes, NUL/control characters, case-fold or Unicode-normalization collisions, symlinks/hardlinks, devices/FIFOs, unsupported compression/encryption and path-parent conflicts. Do not trust ZIP headers for resource budgets. Count measured compressed/expanded bytes, member count, ratio, path lengths, record lengths, coordinate counts, image decoded pixels and CPU/wall time while streaming. Stop immediately on a limit breach and clean up quarantine safely.

The initial configurable profile must cap compressed packages at 250 MiB, expanded data at 1 GiB, members at 10,000, per-member expansion ratio at 100:1, and nested archive extraction depth at zero. Each cap also has an operator-owned hard safety ceiling. Ratios must handle zero-length entries safely. Version 1 does not unpack archives found inside attachments. Enforce smaller file-class limits and global queue budgets where applicable. Preflight must reserve expanded/temp capacity and inodes, not only compressed upload size.

**AF-07.** Uploaded `index.html`, CSS and SVG are **never** rendered as trusted site code, even if the package claims to be generated by LabAdda. Regenerate the temporary viewer from validated records and sanitized raster previews, under a restrictive sandbox/CSP and protected authorization. Store original potentially active attachment bytes only as inert protected downloads when current site media policy permits; refuse unsupported types for materialization. Never make quarantine a public static folder or allow scanner/renderer subprocesses to escape their bounded, unprivileged execution environment. No archive-provided command, migration, URL fetch or database connection may run.

**AF-08.** Structural inspection must be possible before accepting an import, with a report of validation failures, untrusted attribution, missing dependencies, unsupported types, logical/physical/staging charges, current-policy expiries and eligible destinations. Counts must reveal only the uploader's own package, not inaccessible live-site objects. Hash matching must not confirm whether another user's file exists on the server. Reject incomplete/corrupt packages by default; an explicit supported partial-view mode must mark missing data and disable materialization of affected dependency units.

## Materialization and repeatability

**AF-09.** Materialization creates current-domain records with new server IDs, a validated source namespace, preserved historical attribution as provenance and a currently authenticated importing actor. It must never impersonate a source author, add a member, resurrect a deleted account, revive a revoked session or trust an imported administrative policy. Map dependencies and detect conflicts before writes. Supported initial units are a post plus selected attachments/replies, a private note, an explicitly selected chat segment as archived reference, and a board state into a **new** destination board/workspace where allowed. Inserting arbitrary history into an active chat cursor or overwriting an active collaborative board is not supported in version 1.

**AF-10.** An approved plan fixes archive digest, selection, mappings, destination, audience confirmation, target versions, effective policy, reserved bytes and idempotency key. Revalidate before commit. Duplicate keys return the same result; changed payload/destination under the same key fails. A second intentional import must warn about known lineage duplicates and their quota/retention effects. Cross-site or modified unsigned packages cannot claim trusted lineage exceptions. Imported reminders are off by default and require an explicit new schedule; historical timestamps cannot trigger backdated notifications. Preserve source expiry/hold metadata as history and apply DL-17/DL-23 to current lifecycle, without silently making all imported content immortal.

**AF-11.** Acceptance requires: export → ordinary offline extraction/readability → validated re-upload → read-only view → selected materialization → re-export, with byte hashes and semantic equivalence for declared supported features. Different author IDs and new server IDs are expected; lost attachments, changed drawing geometry, altered Unicode, reordered messages or broadened access are failures. Tests must include partial selections, split packages, compacted boards, expired source content, departed users, private notes, revoked access during download, corruption, malformed ZIPs, interrupted/resumed jobs, duplicate imports and a site with outbound networking blocked. Successful viewing is not proof that materialization or disaster recovery is safe.
