import { useState } from "react";
import { useSession } from "../../session";
import { Button, PageHeader } from "../../ui";
import { PasswordForm } from "./PasswordForm";
import "./profile.css";

/** Shown alone, before anything else, when an administrator chose the first password. */
export function ForcedPasswordChange() {
  const { session, patch, signOut } = useSession();
  const [done, setDone] = useState(false);
  return (
    <main className="profile-forced" id="main">
      <PageHeader
        title="Choose your own password"
        scope={`${session?.user.display_name ?? "You"}, your first password was chosen for you. Replace it with one only you know before you continue.`}
      />
      <PasswordForm
        onChanged={() => {
          setDone(true);
          patch({ must_change_password: false });
        }}
      />
      {!done && (
        <div>
          <Button onClick={() => void signOut()}>Sign out instead</Button>
        </div>
      )}
    </main>
  );
}
