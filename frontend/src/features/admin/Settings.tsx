import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api";
import { invalidate } from "../../generation";
import { BASE } from "../../config";
import { UsageReaders } from "../../components/UsageReaders";
import { ErrorState, PageHeader, Skeleton } from "../../ui";
import { SettingsGroups } from "./SettingsGroups";
import type { SettingsPayload } from "./settingsTypes";
import { useAdminData } from "./useAdminData";

type Account = { id: string; username: string; display_name: string; is_active: boolean; is_admin: boolean };

function Delegations() {
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
  if (error) return <ErrorState message={error} onRetry={() => setRetry(retry + 1)} />;
  return users ? <UsageReaders users={users} /> : <Skeleton label="Loading accounts for delegations" />;
}

/** Effective limits in plain words, and time-limited operational delegations. */
export function Settings() {
  const { data, error, reload } = useAdminData<SettingsPayload>("/admin/settings");
  return (
    <>
      <PageHeader
        title="Settings"
        scope="The limits this site runs with, and time-limited operational access."
        helpHref={BASE + "/admin/help"}
      />
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        <Skeleton label="Loading settings" />
      ) : (
        <>
          <SettingsGroups groups={data.groups} />
        </>
      )}
      <Delegations />
    </>
  );
}
