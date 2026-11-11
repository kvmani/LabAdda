export type User = { id: string; username: string; display_name: string; is_active: boolean };
export type SessionInfo = {
  user: User & { is_admin: boolean; home_workspace_id: string | null };
  csrf_token: string;
  timezone: string;
  instance: string;
  limits: { max_attachments: number; max_attachment_bytes: number };
};
export type Workspace = {
  id: string;
  kind: "org" | "project" | "group";
  name: string;
  description: string;
  parent_id: string | null;
  archived: boolean;
  posting_policy: "open" | "read_only";
  role: "member" | "steward" | null;
  inherited: boolean;
  can_write: boolean;
  can_moderate: boolean;
  unread_chat: number;
};
export type Attachment = {
  id: string;
  display_name: string;
  media_type: string;
  size: number;
  url: string;
  preview_url: string | null;
};
export type Post = {
  id: string;
  seq: number;
  workspace_id: string;
  parent_id: string | null;
  kind: "discussion" | "official";
  body: string;
  pinned: boolean;
  due_at: string | null;
  remind_at: string | null;
  created_at: string;
  edited_at: string | null;
  author: User | null;
  attachments: Attachment[];
  replies: Post[];
  can_edit: boolean;
  can_remove: boolean;
  snapshot?: {
    source_revision: number;
    source_name: string | null;
    source_workspace_id: string | null;
  } | null;
};
export type ChatMessage = {
  attachments: Attachment[];
  parent_id: string | null;
  id: string;
  seq: number;
  workspace_id: string;
  body: string;
  client_id: string;
  created_at: string;
  author: User | null;
};
/** A board coordinate: x then y, in board units. */
export type Point = [number, number];
export type StrokeData = { points: Point[]; color: string; width: number };
/** Typed notes and stickies share one shape. */
export type NoteData = { x: number; y: number; text: string; color: string };
export type BoardImageData = { x: number; y: number; w: number; h: number; asset_id: string };
/** A board object's kind with the data the server validated for that kind (api/board.py). */
export type BoardObjectContent =
  | { kind: "stroke"; data: StrokeData }
  | { kind: "text" | "sticky"; data: NoteData }
  | { kind: "image"; data: BoardImageData };
export type BoardObjectKind = BoardObjectContent["kind"];
export type BoardObjectData = BoardObjectContent["data"];
/** Fields an operation may carry; which ones depends on the operation type. */
export type BoardOpPayload = {
  kind?: BoardObjectKind;
  data?: BoardObjectData;
  author?: string;
  dx?: number;
  dy?: number;
  target_revision?: number;
  target_type?: string;
};
export type BoardOp = {
  revision: number;
  epoch: number;
  op_id: string;
  actor_id: string;
  type: string;
  object_id: string;
  payload: BoardOpPayload;
};

/** Where opening a notification leads (api/notifications.py). */
export type NotificationLink =
  | { view: "notes"; id: string }
  | { view: "noticeboard"; workspace_id: string; post_id: string }
  | { view: "chat"; workspace_id: string; seq: number };
export type OpenedNotification = { id: string; kind: string; link: NotificationLink };

type SearchHit = { id: string; body: string; created_at: string; author: User | null };
/** Workspace-local search (GET /workspaces/{id}/search). */
export type SearchResults = {
  counts: { posts: number; chat: number };
  posts: (SearchHit & { parent_id: string | null })[];
  chat: (SearchHit & { seq: number })[];
};

/** A page of workspace chat (GET /workspaces/{id}/chat). */
export type ChatPage = { messages: ChatMessage[]; has_more: boolean };
/** A person with their direct role in one workspace. */
export type WorkspaceMember = User & { role: "member" | "steward" };
