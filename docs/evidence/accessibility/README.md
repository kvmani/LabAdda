# Automated accessibility audit

Captured by `e2e/accessibility.mjs` on a fresh disposable HTTP `scripts/proxy-stack.sh` stack, at root and `/labadda-staging`. [axe-findings.json](axe-findings.json) lists the 24 audited views (12 per instance); none has a violation.

- axe-core 4.10.2, WCAG 2.1 A/AA rule tags. Views: sign-in, noticeboard, whiteboard, chat, group members, My Notes, storage usage, new group, administration, mobile noticeboard (390×844), touch-panel pairing and touch-panel board.
- Keyboard: the first Tab reaches "Skip to main content", Enter moves focus into the main region, and the next 12 focused controls all show a visible indicator.
- Phone width: no horizontal page scroll on the noticeboard or usage page.
- Screenshots: [desktop usage, root](root-desktop-usage.png), [desktop usage, prefix](labadda-staging-desktop-usage.png), [mobile noticeboard, root](root-mobile-noticeboard.png), [mobile noticeboard, prefix](labadda-staging-mobile-noticeboard.png).

The first run found one serious issue: muted text failed contrast on the active rail highlight. It was fixed by darkening the shared muted-text colour, and the rerun shown here has no findings. Automated rules cover only part of WCAG; a manual screen-reader, zoom and visual review and the physical panel test remain open.
