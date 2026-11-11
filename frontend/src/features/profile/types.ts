import type { AccessPage, StaffRecord } from "../people/types";

export type Profile = { record: StaffRecord; access: AccessPage["memberships"] };

export type OwnSession = {
  id: string;
  browser: string;
  started_at: string;
  last_seen_at: string;
  current: boolean;
};
