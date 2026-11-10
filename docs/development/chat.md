# Colleague chat implementation

Read S3/S8 and the latest roadmap ledger. C4 work proceeds as APIs, threaded web,
attachment APIs, attachment/private-group web qualification; C5 dashboard/settings
follow. Keep each slice runnable and update this guide with its source/test contract.

Current baseline: workspace stream with durable client IDs, per-workspace unread
state, socket delivery and HTTP replay. Groups use the same source policy. Parent
membership and administrator roles never grant access to private groups or siblings.
Board-only sessions never receive chat. No implicit broader sharing of attachments.
