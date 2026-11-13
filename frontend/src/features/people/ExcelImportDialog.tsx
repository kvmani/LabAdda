import { useRef, useState } from "react";
import { errorStatus } from "../../api";
import { Button, Dialog, Skeleton, Tag } from "../../ui";
import type { BulkReceipt } from "./changeTypes";
import { PlanReview } from "./PlanReview";
import { ReceiptSlips } from "./ReceiptSlips";
import {
  MAX_BYTES,
  applyFile,
  describeFailure,
  downloadTemplate,
  reviewFile,
  typeOf,
  type StaffReport,
  type StaffRow,
} from "./staffImport";

type Props = { onClose: () => void; onDenied: () => void; onDone: () => void };
type Phase = "choose" | "reading" | "report" | "saving" | "saved";

const ACCESS_WORDS = {
  code: "Activation code on a printed slip",
  password: "First password from the file, changed at first sign-in",
  off: "Sign-in switched off",
} as const;

function Rules() {
  return (
    <details className="people-import__rules">
      <summary>What the file must contain</summary>
      <ul>
        <li>
          Required on every row: <strong>full_name</strong>, <strong>Group</strong>, <strong>Emp No</strong>{" "}
          and <strong>username</strong>. <strong>email</strong> is the username followed by the site&apos;s
          e-mail domain; leave it blank to fill it in.
        </li>
        <li>
          Division and section are optional. With neither, the person sits directly under the Group. A section
          with no division sits directly under the Group. Nothing is filled in for you.
        </li>
        <li>
          Left blank: Extension and Residence Phone stay empty, is_active means TRUE, role means member, and a
          blank Password gives a printed activation slip.
        </li>
        <li>
          A Password in the file is the first password. It is never shown or kept, and the person must change
          it when they first sign in.
        </li>
        <li>Put admin in the role column only for people who will manage LabAdda.</li>
      </ul>
    </details>
  );
}

function RowList({ rows }: { rows: StaffRow[] }) {
  return (
    <details>
      <summary>{`All ${rows.length} people in the file`}</summary>
      <ul className="people-import__people">
        {rows.map((row) => (
          <li key={row.line}>
            <strong>{`Line ${row.line}: ${row.display_name}`}</strong>
            {` (${row.username}) — ${row.place}. ${ACCESS_WORDS[row.access]}.`}
            {row.role === "admin" && (
              <>
                {" "}
                <Tag tone="danger">Administrator</Tag>
              </>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Problems({ rows }: { rows: StaffRow[] }) {
  const failed = rows.filter((row) => row.errors.length);
  return (
    <section className="people-import__group" aria-label="Rows with problems">
      <h3 className="people-change__heading">{`Rows with problems (${failed.length})`}</h3>
      <p>Nothing was saved. Fix these rows in your spreadsheet, then choose the file again.</p>
      <ul className="people-change__issues">
        {failed.map((row) => (
          <li key={row.line} className="people-import__row">
            <strong>{`Line ${row.line}: ${row.display_name || row.username || "(no name)"}`}</strong>
            <ul>
              {row.errors.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Review({
  report,
  reason,
  onReason,
}: {
  report: StaffReport;
  reason: string;
  onReason: (value: string) => void;
}) {
  const plan = report.plan
    ? { ...report.plan, steps: report.plan.steps.filter((s) => s.summary.startsWith("Create the ")) }
    : null;
  const admins = report.administrators;
  return (
    <div role="region" aria-label="Import report">
      <p role="status">
        {`${report.total} ${report.total === 1 ? "person" : "people"} will be added and ${report.units_to_create.length} ${report.units_to_create.length === 1 ? "unit" : "units"} will be created. All of it is saved together, or none of it.`}
      </p>
      {admins.length > 0 && (
        <p className="people-change__problem" role="alert">
          <Tag tone="danger">Administrator</Tag>
          {` ${admins.join(", ")} will become ${admins.length === 1 ? "an administrator" : "administrators"}. Administrators manage every person and unit in LabAdda. Check this is intended.`}
        </p>
      )}
      <RowList rows={report.rows} />
      <PlanReview plan={plan} checking={false} problem={null} reason={reason} onReason={onReason} />
    </div>
  );
}

/** Upload an Excel (or CSV) staff sheet → read the report → one reason → create everything or nothing. */
export function ExcelImportDialog({ onClose, onDenied, onDone }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("choose");
  const [problem, setProblem] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<StaffReport | null>(null);
  const [reason, setReason] = useState("");
  const [receipt, setReceipt] = useState<BulkReceipt | null>(null);

  function fail(error: unknown) {
    if ([401, 403].includes(errorStatus(error) ?? 0)) onDenied();
    setProblem(describeFailure(error));
  }
  async function choose(chosen: File | undefined) {
    if (!chosen) return;
    setProblem("");
    if (!typeOf(chosen)) return setProblem("Choose an Excel workbook (.xlsx) or a .csv file.");
    if (chosen.size > MAX_BYTES) return setProblem("That file is too large. Staff lists can be up to 1 MiB.");
    setPhase("reading");
    try {
      const result = await reviewFile(chosen);
      setFile(chosen);
      setReport(result);
      setPhase("report");
    } catch (error: unknown) {
      fail(error);
      setPhase(report ? "report" : "choose");
    } finally {
      if (input.current) input.current.value = "";
    }
  }
  async function apply() {
    if (!file || !report?.plan) return;
    if (reason.trim().length < 3) return setProblem("Give a reason of at least 3 characters.");
    setProblem("");
    setPhase("saving");
    try {
      setReceipt(await applyFile(file, report.plan.digest, reason.trim()));
      setPhase("saved");
    } catch (error: unknown) {
      fail(error);
      setPhase("report");
    }
  }
  async function template() {
    try {
      await downloadTemplate();
    } catch (error: unknown) {
      fail(error);
    }
  }

  const saved = phase === "saved";
  const busy = phase === "saving";
  const ready = Boolean(report?.plan) && !report?.plan?.blockers.length;
  const footer = saved ? (
    <Button
      variant="primary"
      onClick={() => {
        onDone();
        onClose();
      }}
    >
      Done
    </Button>
  ) : (
    <>
      <Button onClick={onClose} disabled={busy}>
        Cancel
      </Button>
      {report && ready && (
        <Button variant="primary" busy={busy} busyLabel="Applying…" onClick={() => void apply()}>
          {`Add ${report.total} ${report.total === 1 ? "person" : "people"}`}
        </Button>
      )}
    </>
  );
  return (
    <Dialog
      open
      title="Import staff from Excel"
      onClose={busy ? () => undefined : onClose}
      size="lg"
      footer={footer}
    >
      {saved && receipt ? (
        <div role="status" className="people-change">
          <p>{`${report?.total ?? 0} people were added.`}</p>
          <ReceiptSlips added={receipt.added} />
        </div>
      ) : (
        <>
          <p>
            Upload an Excel workbook with one row per person. Nothing is saved until you have read the report
            and confirmed. The file itself is not kept.
          </p>
          <Rules />
          <div className="people-actions">
            <Button icon="download" onClick={() => void template()}>
              Download the Excel template
            </Button>
            <Button
              variant={report ? "secondary" : "primary"}
              busy={phase === "reading"}
              busyLabel="Reading file…"
              onClick={() => input.current?.click()}
            >
              {report ? "Choose a different file" : "Choose an Excel file"}
            </Button>
            <input
              ref={input}
              type="file"
              accept=".xlsx,.csv,text/csv"
              hidden
              aria-label="Staff sheet file"
              onChange={(event) => void choose(event.target.files?.[0])}
            />
          </div>
          {phase === "reading" && <Skeleton label="Reading the staff sheet" />}
          {problem && (
            <p className="people-change__problem" role="alert">
              {problem}
            </p>
          )}
          {report && report.errors > 0 && <Problems rows={report.rows} />}
          {report && report.errors === 0 && <Review report={report} reason={reason} onReason={setReason} />}
        </>
      )}
    </Dialog>
  );
}
