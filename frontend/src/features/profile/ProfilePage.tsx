import { BASE } from "../../config";
import { useSession } from "../../session";
import { Card, EmptyState, ErrorState, PageHeader, Skeleton } from "../../ui";
import { calendarDate } from "../people/model";
import { usePeopleData } from "../people/usePeopleData";
import { PasswordForm } from "./PasswordForm";
import { SessionsList } from "./SessionsList";
import type { OwnSession, Profile } from "./types";
import "./profile.css";

const noop = () => undefined;

function Record({ profile }: { profile: Profile }) {
  const person = profile.record;
  const fields: [string, string | null | undefined][] = [
    ["Name", person.display_name],
    ["Username", person.username],
    ["Employee number", person.employee_no],
    ["Designation", person.designation],
    ["Home unit", person.home_unit?.name],
    ["Employment status", person.status.replace(/_/g, " ")],
    ["Work email", person.contact_email],
    ["Phone extension", person.extension ?? person.contact_phone],
    ["Residence phone", person.residence_phone],
    ["Date joined", calendarDate(person.joined_on)],
  ];
  return (
    <dl className="profile-record">
      {fields.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value || "Not recorded"}</dd>
        </div>
      ))}
    </dl>
  );
}

function Access({ profile }: { profile: Profile }) {
  if (!profile.access.length)
    return (
      <EmptyState title="No workspace access yet">
        Ask a steward or an administrator to add you to a unit.
      </EmptyState>
    );
  return (
    <ul className="profile-list">
      {profile.access.map((item) => (
        <li key={item.workspace.id}>
          <span>
            <strong>{item.workspace.name}</strong>
            {item.workspace.archived && " (archived)"}
          </span>
          <span>{item.inherited ? "Inherited from a unit below it" : `Direct ${item.role}`}</span>
        </li>
      ))}
    </ul>
  );
}

/** My profile: the staff record and access (read-only), password change and active sessions. */
export function ProfilePage() {
  const { session } = useSession();
  const profile = usePeopleData<Profile>("/me/profile", noop);
  const sessions = usePeopleData<{ items: OwnSession[] }>("/me/sessions", noop);
  return (
    <div className="profile-page">
      <PageHeader
        title="My profile"
        scope="Only you can see this page. Your record is kept by your administrators."
        helpHref={BASE + "/help/using/my-profile-and-password"}
      />
      <Card title="My record">
        {profile.error ? (
          <ErrorState message={profile.error} onRetry={profile.refresh} />
        ) : !profile.data ? (
          <Skeleton label="Loading your record" />
        ) : (
          <>
            <Record profile={profile.data} />
            <p>To correct a detail, ask an administrator. You cannot edit these fields.</p>
          </>
        )}
      </Card>
      <Card title="My access">
        {profile.error ? (
          <ErrorState message={profile.error} onRetry={profile.refresh} />
        ) : !profile.data ? (
          <Skeleton label="Loading your access" />
        ) : (
          <Access profile={profile.data} />
        )}
      </Card>
      <Card title="Change password">
        <PasswordForm onChanged={sessions.refresh} />
      </Card>
      <Card title="My sessions">
        <SessionsList
          sessions={sessions.data?.items ?? null}
          error={sessions.error}
          timezone={session?.timezone ?? "UTC"}
          onRetry={sessions.refresh}
        />
      </Card>
    </div>
  );
}
