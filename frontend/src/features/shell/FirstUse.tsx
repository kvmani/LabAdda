import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../../api";
import { useSession } from "../../session";
import { Button } from "../../ui";
import { useWorkspaces } from "../../workspaces";

type Notice = {
  heading: string;
  path: string;
  done: { welcome_pending: false } | { whats_new_pending: false };
};

/** A dismissible panel at the top of the page. It never takes focus or blocks the work below it. */
function NoticePanel({ notice, children }: { notice: Notice; children: ReactNode }) {
  const { patch } = useSession();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dismiss = async () => {
    setSaving(true);
    setError(null);
    try {
      await api(notice.path, { method: "POST" });
      patch(notice.done);
    } catch (problem: unknown) {
      setError(errorMessage(problem));
      setSaving(false);
    }
  };
  const panel = useRef<HTMLElement>(null);
  const dismissRef = useRef(dismiss);
  dismissRef.current = dismiss;
  const savingRef = useRef(saving);
  savingRef.current = saving;

  // A native listener: the panel is a landmark, not a control, so React's key props are not used on it.
  useEffect(() => {
    const element = panel.current;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !savingRef.current) void dismissRef.current();
    };
    element?.addEventListener("keydown", onKeyDown);
    return () => element?.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <section className="first-use" aria-labelledby="first-use-heading" ref={panel}>
      <h2 id="first-use-heading" className="first-use__title">
        {notice.heading}
      </h2>
      {children}
      {error && (
        <p className="first-use__error" role="alert">
          {error}
        </p>
      )}
      <div className="first-use__actions">
        <Button variant="primary" busy={saving} busyLabel="Saving…" onClick={() => void dismiss()}>
          Got it, hide this
        </Button>
      </div>
    </section>
  );
}

function Welcome() {
  const { session } = useSession();
  const { workspaces, loading } = useWorkspaces();
  const home = workspaces.find((workspace) => workspace.id === session?.user.home_workspace_id);
  const notice: Notice = {
    heading: `Welcome to LabAdda, ${session?.user.display_name ?? ""}`,
    path: "/me/welcome/dismiss",
    done: { welcome_pending: false },
  };
  return (
    <NoticePanel notice={notice}>
      <p>
        {loading
          ? "Finding your home unit…"
          : home
            ? `Your home unit is ${home.name}. You will find its pages in the list on the left.`
            : "You have not been placed in a unit yet. Ask an administrator, and your pages will appear in the list on the left."}
      </p>
      <ul className="first-use__list">
        <li>
          <strong>Noticeboard</strong> is for posts and announcements that your colleagues should read.
        </li>
        <li>
          <strong>Whiteboard</strong> is a shared drawing space where you sketch ideas together, live.
        </li>
        <li>
          <strong>Chat</strong> is for quick conversation with the people in a space.
        </li>
      </ul>
      <p>
        Stuck at any time? Choose <Link to="/help">Help</Link> in the top bar. This message will not come back
        once you hide it.
      </p>
    </NoticePanel>
  );
}

function WhatsNew() {
  const notice: Notice = {
    heading: "What is new in this release",
    path: "/me/whats-new/seen",
    done: { whats_new_pending: false },
  };
  return (
    <NoticePanel notice={notice}>
      <p>
        LabAdda has been updated. <Link to="/help/whats-new">Read what is new</Link> in plain words.
      </p>
    </NoticePanel>
  );
}

/** The first-sign-in welcome, then, once per release, a pointer to what is new (HP-08). */
export function FirstUse() {
  const { session } = useSession();
  if (session?.welcome_pending) return <Welcome />;
  if (session?.whats_new_pending) return <WhatsNew />;
  return null;
}
