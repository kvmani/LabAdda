---
title: Broadcast messages
summary: Scroll short announcements across the top of every page, and take them down when they no longer matter.
audience: administrator
screen: none
updated: 2026-11-13
---

## What this is for

A broadcast is a short message that scrolls across the top of every page for everyone who is signed in. Use it for news people must notice, such as planned maintenance that pauses saving. You can keep several messages at once. They scroll one after another in the order shown on the Broadcast page. Messages are plain text, up to 300 characters.

Everyone who is signed in can read every broadcast, so never put anything private in one. Board-only screens do not show broadcasts.

## Before you start

Only administrators can open **Broadcast**. Decide whether the message needs a start and end time, or should stay until you turn it off.

## Steps

1. Open **Administration** and choose **Broadcast**.
2. Choose **Add broadcast message**.
3. Type the **Message** and choose its **Level**: Information for general news, Warning for anything that interrupts work.
4. Optionally set **Show from** and **Show until**. Leave both empty to show it now with no end.
5. Choose **Add message**.

To change a message, choose **Edit**. To hide it without losing it, choose **Turn off**; **Turn on** shows it again. Use the arrows in **Order** to move a message earlier or later. To remove a message for good, choose **Delete** and confirm. A deleted message cannot be brought back.

## What happens next

People see new messages within a minute. The messages scroll slowly. A **Pause announcements** button stops the movement, and the scrolling also stops while the pointer is over the strip or the keyboard is on its button. If a person's computer is set to reduce motion, the messages are listed without moving. Screen readers read a message once when it appears or changes.

A new pilot installation starts with one warning: "The software is under pilot testing. Exercise caution in usage! Don't put any sensitive information." It stays until you remove it. To remove it, open **Broadcast** and choose **Turn off** (to keep it for later) or **Delete**. It is never added again by itself. The operator does not need to do anything.

Every add, edit, order change and deletion is recorded in the audit trail with who did it and when. The trail keeps only the length of the text, not the text itself.

## If something goes wrong

- The message is refused. Remove line breaks and unusual symbols, and keep it within 300 characters.
- The end time is refused. It must be in the future and later than the start time.
- The page says someone else changed the message. Close the window, reload the page and try again.
- You cannot add more messages. At most 20 are kept; delete old ones first.

## Related

- [Reading the settings page](settings.md)
- [Reading the Backups page](backups-page.md)
