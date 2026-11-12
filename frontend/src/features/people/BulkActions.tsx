import { useState } from "react";
import { Button, Select } from "../../ui";
import { BulkReviewDialog } from "./BulkReviewDialog";
import type { BulkItem } from "./changeTypes";
import type { Unit } from "./types";

export const MAX_SELECTED = 100;

type Props = {
  selected: string[];
  units: Unit[];
  onClear: () => void;
  onDenied: () => void;
  onDone: () => void;
};

/** Move or suspend the people ticked in the list, as one reviewed change (at most 100). */
export function BulkActions({ selected, units, onClear, onDenied, onDone }: Props) {
  const [unit, setUnit] = useState("");
  const [requests, setRequests] = useState<BulkItem[] | null>(null);
  const [title, setTitle] = useState("");
  if (!selected.length) return null;
  const open = units.filter((item) => item.kind === "org" && !item.archived);
  function review(kind: "move" | "suspend") {
    setTitle(kind === "move" ? "Move the selected people" : "Suspend the selected people");
    setRequests(
      selected.map((id) =>
        kind === "move"
          ? { kind: "transfer", person_id: id, to_unit_id: unit, role: "member" }
          : { kind: "suspend", person_id: id },
      ),
    );
  }
  return (
    <div className="people-actions" role="group" aria-label="Actions for selected people">
      <p role="status">
        {`${selected.length} selected.`}
        {selected.length >= MAX_SELECTED ? ` You can select at most ${MAX_SELECTED} people.` : ""}
      </p>
      <Select
        label="Move to unit"
        placeholder="Choose a unit"
        value={unit}
        options={open.map((item) => ({ value: item.id, label: item.name }))}
        onChange={(event) => setUnit(event.target.value)}
      />
      <Button disabled={!unit} onClick={() => review("move")}>
        Review move
      </Button>
      <Button onClick={() => review("suspend")}>Review suspension</Button>
      <Button variant="quiet" onClick={onClear}>
        Clear selection
      </Button>
      {requests && (
        <BulkReviewDialog
          title={title}
          requests={requests}
          onClose={() => setRequests(null)}
          onDenied={onDenied}
          onDone={() => {
            onClear();
            onDone();
          }}
        />
      )}
    </div>
  );
}
