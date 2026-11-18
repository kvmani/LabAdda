import { Link } from "react-router-dom";
import { Skeleton } from "../../ui";
import { useWorkspaces } from "../../workspaces";
import type { Work, useDashboardOverview } from "./useDashboardOverview";
import type { useHomeTasks } from "./useHomeTasks";

function dueBadge(dueDate: string | null, today: string) {
  if (!dueDate) return null;
  if (dueDate < today) {
    return <span className="wb-badge wb-badge--overdue">Overdue ({dueDate})</span>;
  }
  if (dueDate === today) {
    return <span className="wb-badge wb-badge--due-today">Due today</span>;
  }
  return <span className="wb-badge wb-badge--due">Due {dueDate}</span>;
}

function priorityBadge(priority: string) {
  if (priority === "high") {
    return <span className="wb-badge wb-badge--priority-high">High</span>;
  }
  if (priority === "normal") {
    return <span className="wb-badge wb-badge--priority-medium">Normal</span>;
  }
  return <span className="wb-badge wb-badge--priority-low">Low</span>;
}

type Props = {
  activeTasks: Work[];
  task: ReturnType<typeof useHomeTasks>;
  dashboard: Pick<ReturnType<typeof useDashboardOverview>, "error" | "loading" | "load">;
  todayStr: string;
};
export function HomeTasksCard({ activeTasks, task, dashboard, todayStr }: Props) {
  const { workspaces } = useWorkspaces();
  const {
    notice: taskNotice,
    pending: pendingTask,
    error: taskError,
    toggle: toggleTaskComplete,
    undo: undoTaskComplete,
  } = task;
  const { error: dashError, loading: dashLoading, load: loadDashboard } = dashboard;
  return (
    <section className="wb-card" aria-label="Active tasks and deadlines">
      <div className="wb-card__header">
        <div>
          <h2 className="wb-card__title">
            <span className="wb-card__icon" aria-hidden="true">
              📋
            </span>
            <span>My Tasks & Deadlines</span>
          </h2>
          <p className="wb-card__subtitle">Up to 25 active tasks · Save completion with the checkbox</p>
        </div>
        <Link to="/my-tasks" className="wb-card__link">
          View all tasks →
        </Link>
      </div>

      <div className="wb-card__body">
        {/* Task Completed Feedback Toast */}
        {taskNotice &&
          (!taskNotice.workspaceId || workspaces.some((space) => space.id === taskNotice.workspaceId)) && (
            <div className="wb-task-toast" role="status">
              <span>
                ✓ <strong>{taskNotice.title}</strong> marked as completed!
              </span>
              <button
                type="button"
                className="wb-task-toast__undo"
                disabled={pendingTask !== null}
                onClick={() => void undoTaskComplete()}
              >
                Undo
              </button>
            </div>
          )}

        {taskError && <p role="alert">{taskError}</p>}
        {dashError ? (
          <p role="alert">
            {dashError}{" "}
            <button type="button" onClick={() => void loadDashboard()}>
              Retry overview
            </button>
          </p>
        ) : dashLoading ? (
          <Skeleton label="Loading your tasks" />
        ) : activeTasks.length === 0 ? (
          <div className="wb-empty">
            <p className="wb-empty__text">No active tasks in this loaded view.</p>
            <Link to="/todos" className="ui-button ui-button--secondary ui-button--sm">
              + Create a task
            </Link>
          </div>
        ) : (
          <ul className="wb-task-list">
            {activeTasks.map((task) => {
              const isDone = task.status === "done";
              return (
                <li key={task.id} className={`wb-task-item ${isDone ? "wb-task-item--done" : ""}`}>
                  <button
                    type="button"
                    className="wb-task-checkbox"
                    disabled={pendingTask !== null}
                    onClick={() => void toggleTaskComplete(task)}
                    title="Mark task as completed"
                    aria-label={`Mark task completed: ${task.title}`}
                  >
                    <span className="wb-task-checkbox__mark" aria-hidden="true">
                      ✓
                    </span>
                  </button>
                  <div className="wb-task-item__content">
                    <Link
                      to={task.workspace_id ? `/w/${task.workspace_id}/todos` : "/todos"}
                      className="wb-task-item__title"
                    >
                      {task.title}
                    </Link>
                    <div className="wb-task-item__meta">
                      {priorityBadge(task.priority)}
                      {dueBadge(task.due_date, todayStr)}
                      <span className="wb-task-item__space">
                        {task.workspace_name ? (
                          <Link to={`/w/${task.workspace_id}/todos`}>{task.workspace_name}</Link>
                        ) : (
                          "Private list"
                        )}
                        {" · "}
                        {task.list_title}
                      </span>
                    </div>
                  </div>
                  <Link
                    to={task.workspace_id ? `/w/${task.workspace_id}/todos` : "/todos"}
                    className="wb-task-item__action"
                    aria-label={`Open task: ${task.title}`}
                  >
                    Open →
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
