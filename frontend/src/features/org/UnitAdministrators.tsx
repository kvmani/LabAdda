import { useState } from "react";
import { Button, ErrorState, Skeleton } from "../../ui";
import { usePeopleData } from "../people/usePeopleData";
import { WithdrawUnitAdminDialog } from "../people/UnitAdminDialogs";

type Appointment = {
  id: string;
  person: { id: string; name: string };
  unit: { id: string; name: string; archived: boolean };
  granted_by: string;
  granted_at: string;
};

/** PO-24: who has been appointed to administer which unit. Site administrators appoint from a person's page. */
export function UnitAdministrators({ onDenied, onChanged }: { onDenied: () => void; onChanged: () => void }) {
  const list = usePeopleData<{ items: Appointment[] }>("/admin/org/unit-admins", onDenied);
  const [ending, setEnding] = useState<Appointment | null>(null);
  if (list.error) return <ErrorState message={list.error} onRetry={list.refresh} />;
  if (!list.data) return <Skeleton lines={2} />;
  return (
    <section aria-label="Unit administrators" className="org-admins">
      <h2 className="org-panel__heading">Unit administrators</h2>
      <p>
        A unit administrator manages people and units in the unit they were appointed to and below it. They
        never see its posts, chat, notes, files or board. Appoint one from a person&apos;s page.
      </p>
      {list.data.items.length ? (
        <ul className="org-panel__people">
          {list.data.items.map((item) => (
            <li key={item.id}>
              <span>
                {item.person.name} administers {item.unit.name}
                {item.unit.archived ? " (closed)" : ""}. Appointed by {item.granted_by} on{" "}
                {item.granted_at.slice(0, 10)}.
              </span>
              <Button variant="quiet" onClick={() => setEnding(item)}>
                {`Withdraw ${item.person.name} from ${item.unit.name}`}
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p>No unit administrators have been appointed.</p>
      )}
      {ending && (
        <WithdrawUnitAdminDialog
          person={ending.person}
          unit={ending.unit}
          onClose={() => setEnding(null)}
          onDenied={onDenied}
          onDone={onChanged}
        />
      )}
    </section>
  );
}
