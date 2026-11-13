export type BroadcastLevel = "info" | "warning";
export type BroadcastStatus = "showing" | "scheduled" | "ended" | "off";

/** What every signed-in person receives: only messages on screen right now. */
export type SiteMessage = { id: number; message: string; level: BroadcastLevel };

/** The administrator's view of one broadcast (docs/API.md, AD-11). */
export type Broadcast = {
  id: number;
  message: string;
  level: BroadcastLevel;
  starts_at: string | null;
  ends_at: string | null;
  active: boolean;
  position: number;
  status: BroadcastStatus;
  revision: number;
};
export type BroadcastList = { broadcasts: Broadcast[]; max_length: number };
