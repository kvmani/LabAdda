import { TaskEditor } from "../components/TaskEditor";
import { TodoTaskCard } from "../components/TodoTaskCard";
import type { Workspace } from "../types";
import { Button, Card, EmptyState, ErrorState, PageHeader, Skeleton, TextInput } from "../ui";
import { useTodos, type Todos as TodoState } from "./useTodos";
import "./todos.css";

type ViewProps = { todos: TodoState; writable: boolean };

function ListsCard({ todos, writable }: ViewProps) {
  const { lists, selected, busy, loading, unconfirmed } = todos;
  return (
    <Card
      title="Lists"
      level={3}
      actions={
        <Button icon="refresh" onClick={() => todos.loadLists()}>
          Refresh lists
        </Button>
      }
    >
      <div className="todos__stack">
        {writable && (
          <form className="todos__inline" onSubmit={todos.createList}>
            <TextInput
              label="New list title"
              maxLength={200}
              disabled={busy || unconfirmed}
              value={todos.title}
              onChange={(e) => todos.setTitle(e.target.value)}
            />
            <Button variant="primary" type="submit" disabled={busy || !todos.title.trim()}>
              {unconfirmed ? "Retry same list creation" : "Create list"}
            </Button>
          </form>
        )}
        {unconfirmed && (
          <p className="todos__muted">List creation is unconfirmed. Retry the same request to recover it.</p>
        )}
        {loading ? (
          <Skeleton lines={3} label="Loading lists…" />
        ) : lists.length === 0 ? (
          <EmptyState title="No to-do lists in this scope yet.">
            {writable ? "Create a list above to start adding tasks." : "Lists will appear here."}
          </EmptyState>
        ) : (
          <nav aria-label="To-do lists">
            <ul className="todos__lists">
              {lists.map((row) => (
                <li key={row.id}>
                  <Button
                    variant={selected?.id === row.id ? "primary" : "secondary"}
                    aria-pressed={selected?.id === row.id}
                    disabled={busy}
                    onClick={() => todos.choose(row)}
                  >
                    {row.title}
                  </Button>
                </li>
              ))}
            </ul>
          </nav>
        )}
        {todos.listCursor && (
          <div>
            <Button onClick={() => todos.loadLists(todos.listCursor!)}>More lists</Button>
          </div>
        )}
      </div>
    </Card>
  );
}

function RenameForm({ todos, writable }: ViewProps) {
  const { busy, renameConflict } = todos;
  return (
    <div className="todos__stack">
      {writable && (
        <form className="todos__inline" onSubmit={todos.renameList}>
          <TextInput
            label="List name"
            maxLength={200}
            value={todos.rename}
            onChange={(e) => todos.setRename(e.target.value)}
          />
          <Button type="submit" disabled={busy || !todos.rename.trim()}>
            Rename list
          </Button>
        </form>
      )}
      {renameConflict && (
        <p className="todos__muted">
          Your list-name draft is kept. Loading the latest list will replace this draft.
        </p>
      )}
      {renameConflict && writable && (
        <div>
          <Button disabled={busy} onClick={todos.loadLatestList}>
            Load latest list (replaces draft)
          </Button>
        </div>
      )}
    </div>
  );
}

function SelectedList({ todos, writable, ws }: ViewProps & { ws?: Workspace }) {
  const { tasks, taskLoading, editing, creating } = todos;
  const selected = todos.selected!;
  return (
    <section className="todos__selected" aria-label="Selected to-do list">
      <Card
        title={selected.title}
        level={3}
        actions={
          <>
            <Button icon="refresh" onClick={() => todos.loadTasks(selected.id)}>
              Refresh tasks
            </Button>
            {writable && (
              <Button variant="primary" icon="plus" onClick={todos.openNewTaskEditor}>
                New task
              </Button>
            )}
          </>
        }
      >
        <RenameForm todos={todos} writable={writable} />
      </Card>
      {taskLoading && <Skeleton lines={3} label="Loading tasks…" />}
      {!taskLoading && tasks.length === 0 && (
        <EmptyState title="No tasks on this page.">
          {writable ? "Choose New task to add the first one." : undefined}
        </EmptyState>
      )}
      <ul className="todo-task-list">
        {tasks.map((task) => (
          <TodoTaskCard
            key={task.id}
            task={task}
            listId={selected.id}
            writable={writable}
            workspaceId={ws?.id}
            reload={() => todos.reloadTasksIfStill(selected.id)}
            edit={() => todos.openTaskEditor(task)}
          />
        ))}
      </ul>
      {todos.taskCursor && (
        <div>
          <Button onClick={() => todos.loadTasks(selected.id, todos.taskCursor!)}>More tasks</Button>
        </div>
      )}
      {writable && (creating || editing) && (
        <TaskEditor
          key={todos.editorKey}
          listId={selected.id}
          initial={editing}
          cancel={todos.cancelEditor}
          saved={() => todos.editorSaved(selected.id)}
        />
      )}
    </section>
  );
}

function SharedUpdatesNotice({ todos }: { todos: TodoState }) {
  return (
    <div className="todos__notice" role="status">
      <span>
        Shared tasks or discussion may have changed. Refresh to check the latest saved work. Your drafts are
        kept.
      </span>
      <Button disabled={todos.loading || todos.taskLoading || todos.busy} onClick={todos.refreshShared}>
        Check shared updates
      </Button>
    </div>
  );
}

export function Todos({ ws }: { ws?: Workspace }) {
  const todos = useTodos(ws);
  const writable = ws ? ws.can_write && !ws.archived : true;
  const audience = ws
    ? `Shared with readers of ${ws.name}.`
    : "Private to you. Administrators and colleagues cannot open these lists.";
  return (
    <section className="todos">
      {ws ? (
        <h2 className="todos__heading">To-do lists</h2>
      ) : (
        <PageHeader title="My To-do Lists" scope={audience} />
      )}
      {ws && <p className="todos__muted">{audience}</p>}
      {ws && todos.updates.pending && <SharedUpdatesNotice todos={todos} />}
      {!writable && <p className="todos__muted">This workspace is read-only. You can read its tasks.</p>}
      {todos.error && <ErrorState message={todos.error} title="Something went wrong" />}
      {todos.message && <p role="status">{todos.message}</p>}
      <ListsCard todos={todos} writable={writable} />
      {todos.selected && <SelectedList todos={todos} writable={writable} ws={ws} />}
    </section>
  );
}
