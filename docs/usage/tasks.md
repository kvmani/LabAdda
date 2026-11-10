# Using to-do lists

Open **My To-do Lists** for private lists, or a workspace's **Tasks** tab for lists
shared with that workspace's readers. Sections, divisions, projects and groups all
use the same task interface. Being a division member does not reveal child-section
lists; personal lists are visible only to their owner.

Create a named list, select it, then choose **New task**. Tasks support a title,
description, calendar due date, priority and checklist. Edit a task and check
**Task completed** to finish it; uncheck it to reopen it. Read-only/archived spaces
allow reading, with editing controls hidden. Due dates do not send reminders in C1.

**Refresh lists** and **Refresh tasks** fetch current data. More-list/task buttons
page through bounded results. If a colleague edits the same task/list first, your
draft remains visible. Copy changes you want to keep, then use **Load latest…** to
replace the draft with the current server version before editing again.

If creation is unconfirmed, the original fields stay frozen. **Retry same…** uses
the original request ID, recovering the same created resource rather than creating
a duplicate. Keep the view open until this is resolved: drafts and these retry IDs
are held in the open view, not saved across closing/reloading/navigating away.

Automatic reminders and deletion are later stages. Shared update notices are described below.

## Workflow and history

Use **Workflow state** to select To do, In progress, Blocked or Done. The completion
checkbox mirrors Done; reopening returns to To do. **View task history** shows who
changed fields, previous/new values and revision time. Older changes are available
in bounded pages. Editing a field retains its old value in history; it does not
purge it. History follows the same personal/workspace permissions as the task.
For tasks predating history tracking, a baseline explains that earlier changes and
authors were not recorded. Refresh tasks to fetch a colleague's latest edits;
shared update notices prompt you to review changes.

## Assigning work and My Tasks

Choose **Change assignee** on a task, find an eligible colleague and **Save assignment**.
Only active readers of that workspace can be selected; personal lists offer only
the owner. Assignment does not grant membership or reveal a private list. Use
**Unassigned** to clear responsibility. A read-only workspace cannot be reassigned.

If the task changed or an assignment reply was lost, your choice is retained but
blind retry is blocked. **Reload task assignment** loads the current task and
revision, discarding the pending choice. Review the result before assigning again.
History records who changed responsibility and the previous/new colleague.

**My Tasks** combines all your personal tasks with shared tasks assigned to you.
Filter by workflow state and open a source list to act on a task. Personal tasks
remain here even when unassigned. Losing workspace access hides its shared tasks;
it does not erase their recorded responsibility or history. Refresh loads current
results; a shared-update notice prompts you when shared work may have changed. Assignment sends no automatic
notification in this slice. If access changes during loading, restart with Refresh
My Tasks rather than continuing an obsolete page.

## Discussing a task

Use **View comments**, write a plain-text comment and **Post comment**. Colleagues
with access to the same shared task can read its discussion; personal task comments
remain owner-only. Refresh comments to see new discussion; older entries are paged.
Read-only spaces hide posting controls. Comments do not change the task field
revision, so discussion alone will not conflict with a pending task edit.

If posting is unconfirmed, the original text stays frozen and **Retry same comment**
recovers the same request. Drafts survive same-list task refresh and task field edits;
keep the view open until posting is confirmed. Navigation/reload discards in-memory
drafts/request IDs. Comments preserve newlines and render HTML-looking text safely
as text. This slice provides no comment editing, deletion, attachments, automatic
notifications or automatic content merging.

## Shared update notices

Shared task and discussion changes now send a live **may have changed** notice.
Reconnecting also shows a notice because updates may have been missed. Choose
**Check shared updates** to refresh the displayed task cards while keeping your
open task editor, assignment choice and comment draft. This keeps your current
page; use **Refresh tasks** to return to the first page and find newly created
tasks. Refresh open comments separately to load the latest discussion. My Tasks
has its own refresh notice for shared work.

A changed task revision requires reviewing/reloading a pending assignment before
saving; your choice is retained until that explicit reload. Failed refreshes leave
the update notice pending. New signals during a refresh also leave it pending.
Personal lists do not send live signals across tabs in this stage. Drafts remain
in memory and do not survive navigation or a page reload.

## Turn a conversation into a task

Choose **Create task** on a noticeboard post or chat message. Review the suggested
title/description, choose your personal lists or a writable workspace, then select
a destination list. The audience is shown before saving. A different workspace
requires checking the audience confirmation. Changing destination/list resets
that choice. If no list exists, create one in the destination and reopen the form.

The task is a reviewed copy: later conversation edits do not change it. Attachments
are not copied. Use ordinary task controls after creation for dates, checklists,
workflow and assignment. If saving is unconfirmed, keep the form open and choose
**Retry same task copy**; the original text/destination stay frozen to prevent
unintended copies. Closing or navigating away discards in-memory retry state.

Converted tasks offer **View source reference**. Only people who can currently
read both the task and the original conversation can open its current text.
Someone who can read a reviewed division task may still be unable to open its
section-only source. Missing/removed/inaccessible sources show the same unavailable
message; the reviewed task stays available under its own list permissions. Source
text is displayed as plain text. Reply conversion is a later slice; board references are described below.

## Research-plan tasks from a whiteboard

After adding plan content, choose **Create task from board** in the normal
whiteboard toolbar. Describe the followup, choose a personal/shared list and review
the recorded board epoch/revision. A different workspace still requires explicit
audience confirmation. Drawing content, images and board names are not copied
into the task text.

If the board changes before saving, the task draft is kept and saving is blocked.
Review the board, then choose **Load latest board context (keeps draft)**. This
updates the context and resets audience confirmation. If the result is unconfirmed,
**Retry same task copy** recovers the original task and context even if colleagues
have since added ink or restored the board.

**View source reference** on the task shows its recorded context and the board's
current context separately, then offers **Open source board**. That link opens the
live board; it is not a saved image or historical rendering. Use the existing
snapshot publishing flow when an immutable image copy is needed. Current task AND
board access are required to inspect context. Later edits/restores do not rewrite
the task reference. Board-only touch sessions cannot create or read task references.
