# Synthetic upload recovery

Chromium screenshots from `e2e/upload-recovery-ui.mjs` on the disposable root/prefix proxy stack. The proxy-facing browser deliberately loses a committed upload response; recovery controls retain the request identity. No real accounts or files are used.

- [Noticeboard, root](notice-root.png)
- [Noticeboard, prefix](notice-prefix.png)
- [Board, mobile root](board-root-mobile.png)
- [Board, mobile prefix](board-prefix-mobile.png)

Checks also cover truncated JSON after successful headers, explicit same-file retries, one Asset per intended file and durable posting/board placement. File bytes/retry controls remain in view memory only; keep the view open until resolved. Dismissal does not delete server content. These screenshots do not establish physical-panel or accessibility acceptance.
