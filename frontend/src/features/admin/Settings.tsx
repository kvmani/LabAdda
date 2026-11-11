import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api";
import { invalidate } from "../../generation";
import { BASE } from "../../config";
import { UsageReaders } from "../../components/UsageReaders";
import { ErrorState, PageHeader, Skeleton } from "../../ui";

type Account = { id: string; username: string; display_name: string; is_active: boolean; is_admin: boolean };

/** Existing delegation tools; general site settings arrive in A7. */
export function Settings() {
  const [users, setUsers] = useState<Account[] | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    const request = ++generation.current;
    setUsers(null);
    setError("");
    api<{ users: Account[] }>("/admin/users")
      .then((result) => {
        if (request === generation.current) setUsers(result.users);
      })
      .catch((failure: unknown) => {
        if (request === generation.current) setError(errorMessage(failure));
      });
    return () => invalidate(generation);
  }, [retry]);
  return (
    <>
      <PageHeader
        title="Settings"
        scope="Time-limited operational delegations; general site settings are not available yet."
        helpHref={BASE + "/admin/help"}
      />
      {error ? (
        <ErrorState message={error} onRetry={() => setRetry(retry + 1)} />
      ) : users ? (
        <UsageReaders users={users} />
      ) : (
        <Skeleton label="Loading accounts for delegations" />
      )}
    </>
  );
}
