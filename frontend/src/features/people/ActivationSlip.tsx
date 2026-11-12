import { BASE } from "../../config";
import { Button } from "../../ui";

type SlipProps = {
  displayName: string;
  username: string;
  code: string;
  expiresAt: string;
};

function expiry(value: string): string {
  const instant = new Date(value);
  if (!Number.isFinite(instant.getTime())) return "Unknown";
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(instant);
}

/** The one time the code is shown: print it or copy it now; it cannot be shown again. */
export function ActivationSlip({ displayName, username, code, expiresAt }: SlipProps) {
  const address = `${window.location.origin}${BASE}/activate`;
  return (
    <div className="people-slip-wrap">
      <p role="status">
        The account is ready. This activation code is shown only once. Print the slip or copy the code now,
        and hand it to the person privately.
      </p>
      <section className="people-slip" aria-label="Activation slip">
        <h3>LabAdda activation slip</h3>
        <dl className="people-record">
          <div>
            <dt>Name</dt>
            <dd>{displayName}</dd>
          </div>
          <div>
            <dt>Username</dt>
            <dd>{username}</dd>
          </div>
          <div>
            <dt>Activation code</dt>
            <dd className="people-slip__code">{code}</dd>
          </div>
          <div>
            <dt>Use before</dt>
            <dd>{expiry(expiresAt)}</dd>
          </div>
          <div>
            <dt>Sign-in address</dt>
            <dd>{address}</dd>
          </div>
        </dl>
        <p>Open the sign-in address, enter the code and choose your own password.</p>
      </section>
      <Button icon="download" onClick={() => window.print()}>
        Print activation slip
      </Button>
    </div>
  );
}
