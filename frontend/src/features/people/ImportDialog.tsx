import { useMemo, useRef, useState } from "react";
import { api, errorMessage, errorStatus } from "../../api";
import { Button, Checkbox, Dialog, Skeleton, Tag } from "../../ui";
import { BulkReviewDialog } from "./BulkReviewDialog";
import type { BulkItem, ImportReport, ImportRow } from "./changeTypes";

const MAX_BYTES = 1024 * 1024;
const GROUPS: { key: ImportRow["group"]; title: string }[] = [
  { key: "add", title: "New people to add" },
  { key: "transfer", title: "People who move to another unit" },
  { key: "change", title: "People whose details change" },
  { key: "errors", title: "Rows with problems (not applied)" },
];

type Props = { onClose: () => void; onDenied: () => void; onDone: () => void };

function RowItem({ row, checked, onToggle }: { row: ImportRow; checked: boolean; onToggle: () => void }) {
  const name = row.display_name || row.username;
  const failed = row.group === "errors";
  return (
    <li className="people-import__row">
      {failed ? (
        <strong>{`Line ${row.line}: ${name}`}</strong>
      ) : (
        <Checkbox label={`Line ${row.line}: ${name}`} checked={checked} onChange={onToggle} />
      )}
      {failed && (
        <ul>
          {row.errors.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
      {!failed && (
        <ul>
          {row.summary.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
      {row.warnings.map((text) => (
        <p key={text}>
          <Tag tone="warn">Check</Tag> {text}
        </p>
      ))}
    </li>
  );
}

function Group({
  title,
  rows,
  selected,
  onToggle,
  onAll,
}: {
  title: string;
  rows: ImportRow[];
  selected: Set<number>;
  onToggle: (line: number) => void;
  onAll: (rows: ImportRow[], on: boolean) => void;
}) {
  if (!rows.length) return null;
  const failed = rows[0]?.group === "errors";
  const all = rows.every((row) => selected.has(row.line));
  return (
    <section className="people-import__group" aria-label={title}>
      <h3 className="people-change__heading">{`${title} (${rows.length})`}</h3>
      {!failed && (
        <Checkbox label={`Select all in “${title}”`} checked={all} onChange={() => onAll(rows, !all)} />
      )}
      <ul className="people-change__issues">
        {rows.map((row) => (
          <RowItem
            key={row.line}
            row={row}
            checked={selected.has(row.line)}
            onToggle={() => onToggle(row.line)}
          />
        ))}
      </ul>
    </section>
  );
}

/** Upload a staff list → read the dry-run report → choose rows → review → apply → activation slips. */
export function ImportDialog({ onClose, onDenied, onDone }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [report, setReport] = useState<ImportReport | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [reviewing, setReviewing] = useState(false);

  const requests = useMemo<BulkItem[]>(
    () => (report?.rows ?? []).filter((row) => selected.has(row.line)).flatMap((row) => row.requests),
    [report, selected],
  );

  async function upload(file: File | undefined) {
    if (!file) return;
    setProblem("");
    if (!file.name.toLowerCase().endsWith(".csv"))
      return setProblem("Choose a .csv file. In your spreadsheet, use Save As, CSV UTF-8.");
    if (file.size > MAX_BYTES)
      return setProblem("That file is too large. Staff lists can be up to 1 MiB and 2,000 rows.");
    setBusy(true);
    try {
      const result = await api<ImportReport>("/admin/changes/import/preview", {
        raw: { data: file, type: "text/csv" },
      });
      setReport(result);
      setSelected(new Set(result.rows.filter((row) => row.group !== "errors").map((row) => row.line)));
    } catch (error: unknown) {
      if ([401, 403].includes(errorStatus(error) ?? 0)) onDenied();
      setProblem(errorMessage(error));
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  async function template() {
    try {
      const blob = await api<Blob>("/admin/changes/import/template", { responseType: "blob" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "staff-list-template.csv";
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (error: unknown) {
      setProblem(errorMessage(error));
    }
  }
  function toggle(line: number) {
    const next = new Set(selected);
    if (!next.delete(line)) next.add(line);
    setSelected(next);
  }
  function toggleAll(rows: ImportRow[], on: boolean) {
    const next = new Set(selected);
    for (const row of rows)
      if (on) next.add(row.line);
      else next.delete(row.line);
    setSelected(next);
  }

  if (reviewing)
    return (
      <BulkReviewDialog
        title="Review the staff list changes"
        requests={requests}
        onClose={onClose}
        onBack={() => setReviewing(false)}
        onDenied={onDenied}
        onDone={onDone}
      />
    );
  const nothing = report !== null && !report.rows.length;
  return (
    <Dialog
      open
      title="Import a staff list"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          {report && (
            <Button variant="primary" disabled={!requests.length} onClick={() => setReviewing(true)}>
              {`Review ${requests.length} selected ${requests.length === 1 ? "row" : "rows"}`}
            </Button>
          )}
        </>
      }
    >
      <p>
        Upload a CSV file of staff. Nothing is saved until you have read the report, chosen the rows and
        confirmed. The file itself is not kept.
      </p>
      <div className="people-actions">
        <Button icon="download" onClick={() => void template()}>
          Download the template
        </Button>
        <Button
          variant={report ? "secondary" : "primary"}
          busy={busy}
          busyLabel="Reading file…"
          onClick={() => input.current?.click()}
        >
          {report ? "Choose a different file" : "Choose a CSV file"}
        </Button>
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          hidden
          aria-label="Staff list CSV file"
          onChange={(event) => void upload(event.target.files?.[0])}
        />
      </div>
      {busy && <Skeleton label="Reading the staff list" />}
      {problem && (
        <p className="people-change__problem" role="alert">
          {problem}
        </p>
      )}
      {report && (
        <div role="region" aria-label="Import report">
          <p role="status">
            {`${report.counts.add} to add, ${report.counts.transfer} to move, ${report.counts.change} to change, ${report.counts.errors} with problems, ${report.counts.unchanged} already up to date.`}
          </p>
          {nothing && <p>Nothing in this file would change anyone.</p>}
          {GROUPS.map((group) => (
            <Group
              key={group.key}
              title={group.title}
              rows={report.rows.filter((row) => row.group === group.key)}
              selected={selected}
              onToggle={toggle}
              onAll={toggleAll}
            />
          ))}
          {report.absent_total > 0 && (
            <details>
              <summary>{`${report.absent_total} people are not in the file and will not be changed`}</summary>
              <ul>
                {report.absent.map((person) => (
                  <li key={person.username}>{`${person.display_name} (${person.username})`}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </Dialog>
  );
}
