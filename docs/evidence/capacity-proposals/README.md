# Observation-only capacity proposals

Real Chromium screenshots from `e2e/capacity-proposals.mjs`, using only synthetic root/prefix fixtures. The admin proposes a site asset budget and filesystem reserve, previews incomplete measurements and saves an immutable version-two draft. Version-one history remains readable. No live limits, reservations or retention rules are activated.

- [Root preview](preview-root.png)
- [Prefixed preview](preview-prefix.png)
- [Root phone preview](preview-root-mobile.png)
- [Prefixed phone preview](preview-prefix-mobile.png)

Twenty-six checks cover history compatibility, upper-bound labeling, profile-edit/reload invalidation, delayed response handling, unchanged current limits, member denial, mobile overflow/axe and keyboard scrolling. Mobile checks initially found account/workspace table overflow; accessible scroll regions and wrapping fixed it. These previews are current capacity scenarios, not growth predictions or production acceptance.
