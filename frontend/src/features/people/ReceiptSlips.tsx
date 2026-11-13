import { Button } from "../../ui";
import { SlipCard } from "./ActivationSlip";
import type { BulkReceipt } from "./changeTypes";

/** Printable slips for the people who were given an activation code; people with a first password get none. */
export function ReceiptSlips({ added }: { added: BulkReceipt["added"] }) {
  const slips = added.filter((person) => person.activation);
  if (!slips.length) return null;
  return (
    <>
      <p>
        Activation codes are shown only once. Print the slips now and hand each one to its person privately.
      </p>
      <div className="people-slips">
        {slips.map((person) =>
          person.activation ? (
            <SlipCard
              key={person.person_id}
              displayName={person.display_name}
              username={person.username}
              code={person.activation.code}
              expiresAt={person.activation.expires_at}
              label={`Activation slip for ${person.display_name}`}
            />
          ) : null,
        )}
      </div>
      <Button icon="download" onClick={() => window.print()}>
        Print all activation slips
      </Button>
    </>
  );
}
