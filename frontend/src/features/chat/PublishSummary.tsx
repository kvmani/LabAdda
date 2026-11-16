import { useId, useRef, useState, type FormEvent } from "react";
import { api, errorMessage, newId } from "../../api";
import { useWorkspaces } from "../../workspaces";
import type { Workspace } from "../../types";
import { Button, Checkbox, Dialog, Select, TextArea } from "../../ui";

type Props = { source: Workspace; text: string; onClose: () => void };
function useSummary({ source, text, onClose }: Props) {
  const { workspaces } = useWorkspaces();
  const targets = workspaces.filter((workspace) => workspace.can_contribute);
  const [dest, setDest] = useState(
    () => targets.find((target) => target.id === source.id)?.id ?? targets[0]?.id ?? "",
  );
  const [body, setBody] = useState(text);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const clientId = useRef(newId("s"));
  const target = targets.find((workspace) => workspace.id === dest);
  const broader = !!target && target.id !== source.id;
  const blocked = !target || !body.trim() || (broader && !confirmed);
  async function publish(event: FormEvent) {
    event.preventDefault();
    if (blocked || !target) return;
    try {
      await api(`/workspaces/${target.id}/posts`, { body: { body, client_id: clientId.current } });
      onClose();
    } catch (failure: unknown) {
      setError(errorMessage(failure));
    }
  }
  return {
    targets,
    dest,
    setDest,
    body,
    setBody,
    confirmed,
    setConfirmed,
    target,
    broader,
    blocked,
    error,
    publish,
  };
}

function SummaryFields({ source, model }: { source: Workspace; model: ReturnType<typeof useSummary> }) {
  return (
    <>
      {model.targets.length === 0 && (
        <p role="status">You have no workspaces that currently accept your posts.</p>
      )}
      <Select
        label="Destination"
        value={model.target ? model.dest : ""}
        onChange={(event) => {
          model.setDest(event.target.value);
          model.setConfirmed(false);
        }}
        options={[
          { value: "", label: "Choose a destination" },
          ...model.targets.map((target) => ({ value: target.id, label: target.name })),
        ]}
      />
      <TextArea
        label="Summary"
        value={model.body}
        onChange={(event) => model.setBody(event.target.value)}
        rows={4}
      />
      {model.broader && (
        <Checkbox
          label={`I understand this copy will be visible to everyone who can read ${model.target?.name}, a different audience from ${source.name}.`}
          checked={model.confirmed}
          onChange={(event) => model.setConfirmed(event.target.checked)}
        />
      )}
      {model.error && (
        <p className="chat__error" role="alert">
          {model.error}
        </p>
      )}
    </>
  );
}

/** Publishing always names an eligible destination and confirms a different audience. */
export function PublishSummary(props: Props) {
  const model = useSummary(props);
  const formId = useId();
  return (
    <Dialog
      open
      title="Publish summary to a noticeboard"
      onClose={props.onClose}
      footer={
        <>
          <Button variant="quiet" onClick={props.onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form={formId} disabled={model.blocked}>
            {model.target ? `Post to ${model.target.name}` : "Post summary"}
          </Button>
        </>
      }
    >
      <form id={formId} className="chat__form" onSubmit={model.publish} aria-label="Publish chat summary">
        <SummaryFields source={props.source} model={model} />
      </form>
    </Dialog>
  );
}
