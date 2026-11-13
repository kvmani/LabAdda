# Feedback button guide

Contract: [API.md](../API.md#pilot--feedback-button-schema-0039).

| Part | Where |
| --- | --- |
| Submit, validation, shapes | `backend/labadda/feedback.py`, `api/feedback.py` |
| E-mail outbox (smtplib, retry, reasons) | `backend/labadda/feedback_mail.py`, scheduler job `feedback_mail` |
| Version and commit (single place to repoint) | `backend/labadda/buildinfo.py` |
| Health item | `backend/labadda/health/feedback_mail.py` |
| Files | `assets.feedback_id`; stored by `AssetStore.save(..., FEEDBACK_TYPES)` |
| Tests | `backend/tests/test_feedback.py`, `e2e/feedback.mjs` |

Rules: server-filled facts are never read from the request; the list endpoint never returns
message text; every administrator read is audited; mail trouble never fails a submission.
