import { useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "../../api";
import { BASE } from "../../config";
import { useSession } from "../../session";
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  PageHeader,
  Skeleton,
  TextInput,
} from "../../ui";
import { calendarDate } from "../people/model";
import type { StaffRecord } from "../people/types";
import { usePeopleData } from "../people/usePeopleData";
import { PasswordForm } from "./PasswordForm";
import { SessionsList } from "./SessionsList";
import type { OwnSession, Profile } from "./types";
import "./profile.css";

const noop = () => undefined;

function AvatarRow({ person, onRefresh }: { person: StaffRecord; onRefresh: () => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Please select a valid image file (PNG, JPEG, or WebP).");
      return;
    }
    if (file.size > 350 * 1024) {
      setError("Avatar image must be under 350KB. Please choose a smaller photo.");
      return;
    }
    setBusy(true);
    setError("");
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const dataUrl = reader.result as string;
        await api("/me/avatar", { method: "POST", body: { avatar_data: dataUrl } });
        onRefresh();
      } catch (err: unknown) {
        setError(errorMessage(err));
      } finally {
        setBusy(false);
      }
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  async function removeAvatar() {
    setBusy(true);
    setError("");
    try {
      await api("/me/avatar", { method: "DELETE" });
      onRefresh();
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="profile-avatar-row">
      {person.avatar_data ? (
        <img src={person.avatar_data} alt={person.display_name} className="profile-avatar" />
      ) : (
        <div className="profile-avatar">{person.display_name.slice(0, 2).toUpperCase()}</div>
      )}
      <div className="profile-avatar-actions">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          hidden
          onChange={handleFile}
        />
        <Button variant="secondary" size="sm" disabled={busy} onClick={() => fileInputRef.current?.click()}>
          {busy ? "Uploading…" : person.avatar_data ? "Change photo" : "Upload photo"}
        </Button>
        {person.avatar_data && (
          <Button variant="quiet" size="sm" disabled={busy} onClick={removeAvatar}>
            Remove photo
          </Button>
        )}
      </div>
      {error && <p className="chat__error">{error}</p>}
    </div>
  );
}

function EditDetailsDialog({
  person,
  onClose,
  onSaved,
}: {
  person: StaffRecord;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [displayName, setDisplayName] = useState(person.display_name ?? "");
  const [designation, setDesignation] = useState(person.designation ?? "");
  const [specialization, setSpecialization] = useState(person.specialization ?? "");
  const [contactPhone, setContactPhone] = useState(person.contact_phone ?? person.extension ?? "");
  const [mobile, setMobile] = useState(person.mobile ?? "");
  const [alternateEmail, setAlternateEmail] = useState(person.alternate_email ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/me/profile", {
        method: "PATCH",
        body: {
          display_name: displayName.trim() || null,
          designation: designation.trim() || null,
          specialization: specialization.trim() || null,
          contact_phone: contactPhone.trim() || null,
          mobile: mobile.trim() || null,
          alternate_email: alternateEmail.trim() || null,
        },
      });
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      title="Edit my profile details"
      onClose={onClose}
      footer={
        <>
          <Button variant="quiet" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="edit-profile-form" busy={busy} busyLabel="Saving…">
            Save changes
          </Button>
        </>
      }
    >
      <form id="edit-profile-form" className="profile-form" onSubmit={handleSubmit}>
        <TextInput
          label="Display Name"
          value={displayName}
          placeholder={person.username}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        <TextInput
          label="Designation"
          value={designation}
          placeholder="e.g. Principal Scientist"
          onChange={(e) => setDesignation(e.target.value)}
        />
        <Field label="Field of Specialization (keywords)">
          {(control) => (
            <input
              {...control}
              className="ui-input"
              value={specialization}
              placeholder="e.g. Thin Films, Nanomaterials, Coatings"
              onChange={(e) => setSpecialization(e.target.value)}
            />
          )}
        </Field>
        <TextInput
          label="Phone Extension / Office Phone"
          value={contactPhone}
          placeholder="e.g. 4417"
          onChange={(e) => setContactPhone(e.target.value)}
        />
        <TextInput
          label="Mobile Number"
          value={mobile}
          placeholder="e.g. 9876543210"
          onChange={(e) => setMobile(e.target.value)}
        />
        <TextInput
          label="Alternate Email"
          value={alternateEmail}
          placeholder="e.g. personal@external.org"
          onChange={(e) => setAlternateEmail(e.target.value)}
        />
        {error && (
          <p className="chat__error" role="alert">
            {error}
          </p>
        )}
      </form>
    </Dialog>
  );
}

function Record({ profile }: { profile: Profile }) {
  const person = profile.record;
  const fields: [string, string | null | undefined][] = [
    ["Display Name", person.display_name],
    ["Username", person.username],
    ["Employee number", person.employee_no],
    ["Designation", person.designation],
    ["Field of Specialization", person.specialization],
    ["Home unit", person.home_unit?.name],
    ["Employment status", person.status.replace(/_/g, " ")],
    ["Work email", person.contact_email],
    ["Alternate email", person.alternate_email],
    ["Phone extension", person.extension ?? person.contact_phone],
    ["Mobile", person.mobile],
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

/** My profile: self-editable profile details, photo upload, staff record, password change and active sessions. */
export function ProfilePage() {
  const { session } = useSession();
  const profile = usePeopleData<Profile>("/me/profile", noop);
  const sessions = usePeopleData<{ items: OwnSession[] }>("/me/sessions", noop);
  const [editing, setEditing] = useState(false);

  return (
    <div className="profile-page">
      <PageHeader
        title="My profile"
        scope="Only you can see this page. Keep your contact details, designation, and photo current."
        helpHref={BASE + "/help/using/my-profile-and-password"}
        action={
          profile.data && (
            <Button variant="secondary" onClick={() => setEditing(true)}>
              ✏️ Edit my details
            </Button>
          )
        }
      />
      <Card title="My details & photo">
        {profile.error ? (
          <ErrorState message={profile.error} onRetry={profile.refresh} />
        ) : !profile.data ? (
          <Skeleton label="Loading your record" />
        ) : (
          <>
            <AvatarRow person={profile.data.record} onRefresh={profile.refresh} />
            <Record profile={profile.data} />
            <div style={{ marginTop: "1rem" }}>
              <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                ✏️ Edit contact & profile fields
              </Button>
            </div>
          </>
        )}
      </Card>

      {editing && profile.data && (
        <EditDetailsDialog
          person={profile.data.record}
          onClose={() => setEditing(false)}
          onSaved={profile.refresh}
        />
      )}

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
          timezone={session?.timezone ?? "Asia/Kolkata"}
          onRetry={sessions.refresh}
        />
      </Card>
    </div>
  );
}
