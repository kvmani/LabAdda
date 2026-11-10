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

Task comments/live updates, automatic reminders and deletion are later stages.

## Workflow and history

Use **Workflow state** to select To do, In progress, Blocked or Done. The completion
checkbox mirrors Done; reopening returns to To do. **View task history** shows who
changed fields, previous/new values and revision time. Older changes are available
in bounded pages. Editing a field retains its old value in history; it does not
purge it. History follows the same personal/workspace permissions as the task.
For tasks predating history tracking, a baseline explains that earlier changes and
authors were not recorded. Refresh tasks to fetch a colleague's latest edits;
live task updates are a later C2 slice.

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
results; task changes are not yet pushed live. Assignment sends no automatic
notification in this slice. If access changes during loading, restart with Refresh
My Tasks rather than continuing an obsolete page.
