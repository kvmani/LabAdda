import { workflowLabels, type Task } from "./TaskEditor";
import { TaskAssignment } from "./TaskAssignment";
import { TaskComments } from "./TaskComments";
import { TaskHistory } from "./TaskHistory";
import { TaskSource } from "./TaskSource";
import { Button, Card } from "../ui";
import "./task.css";

type Props = {
  task: Task;
  listId: string;
  writable: boolean;
  workspaceId?: string;
  /** Reload the visible tasks after an assignment changes. */
  reload: () => void;
  edit: () => void;
};

/** One task with its assignment, discussion, source and history panels. */
export function TodoTaskCard({ task, listId, writable, workspaceId, reload, edit }: Props) {
  return (
    <li>
      <Card>
        <div className="task-card">
          <h4 className="task-card__title">
            {task.done ? "✓ " : ""}
            {task.title}
          </h4>
          <p className="task-card__meta">
            {workflowLabels[task.status] ?? (task.done ? "Done" : "To do")} · {task.priority} priority
            {task.due_date ? ` · Due ${task.due_date}` : ""}
          </p>
          <p className="task__text">{task.description}</p>
          {task.checklist.length > 0 && (
            <ul className="task-card__checklist">
              {task.checklist.map((item, i) => (
                <li key={i}>
                  {item.done ? "✓" : "○"} {item.title}
                </li>
              ))}
            </ul>
          )}
          <TaskAssignment
            listId={listId}
            taskId={task.id}
            revision={task.revision}
            assignee={task.assignee}
            writable={writable}
            saved={reload}
          />
          <TaskComments listId={listId} taskId={task.id} writable={writable} workspaceId={workspaceId} />
          {task.has_source && <TaskSource listId={listId} taskId={task.id} />}
          <TaskHistory listId={listId} taskId={task.id} revision={task.revision} />
          {writable && (
            <div>
              <Button onClick={edit}>Edit task: {task.title}</Button>
            </div>
          )}
        </div>
      </Card>
    </li>
  );
}
