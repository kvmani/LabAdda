import { socketUrl } from "./config";
import type { BoardOp, ChatMessage } from "./types";

/** An uncommitted stroke another person is drawing; relayed by the server without storing it. */
export type StrokePreview = { points: number[][]; color: string };

/** Messages the server pushes on the socket (see docs/API.md, socket messages). */
export type RealtimeEvent =
  | { type: "hello" | "pong" | "access_changed" }
  | { type: "session_ended"; reason?: string }
  | { type: "error"; code: string }
  | {
      type: "subscribed" | "subscribe_failed" | "revoked" | "noticeboard.changed" | "tasks.changed";
      workspace_id: string;
    }
  | { type: "chat.message"; message: ChatMessage }
  | { type: "board.op"; workspace_id: string; op: BoardOp }
  | { type: "board.epoch"; workspace_id: string; epoch: number }
  | {
      type: "board.preview";
      workspace_id: string;
      actor_id: string;
      stroke: StrokePreview | null;
      preview_id: string;
      done: boolean;
    }
  | { type: "presence"; workspace_id: string; users: { id: string; display_name: string }[] };

function workspaceOf(event: RealtimeEvent): string | undefined {
  if ("workspace_id" in event) return event.workspace_id;
  if (event.type === "chat.message") return event.message.workspace_id;
  return undefined;
}

export type ConnState = "connecting" | "online" | "reconnecting" | "offline";
type Handler = (event: RealtimeEvent) => void;

/** One socket per tab. Subscriptions survive reconnects; callers refetch missed state on "subscribed". */
class Realtime {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<Handler>>();
  private confirmed = new Set<string>();
  private stateListeners = new Set<(s: ConnState) => void>();
  private retry = 0;
  private timer: number | undefined;
  private stopped = true;
  state: ConnState = "offline";

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    this.open();
  }

  stop() {
    this.stopped = true;
    window.clearTimeout(this.timer);
    this.ws?.close();
    this.ws = null;
    this.setState("offline");
  }

  private setState(s: ConnState) {
    this.state = s;
    this.stateListeners.forEach((l) => l(s));
  }

  onState(fn: (s: ConnState) => void) {
    this.stateListeners.add(fn);
    fn(this.state);
    return () => this.stateListeners.delete(fn);
  }

  private open() {
    this.setState(this.retry ? "reconnecting" : "connecting");
    const ws = new WebSocket(socketUrl());
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.setState("online");
      for (const id of this.handlers.keys()) this.send({ type: "subscribe", workspace_id: id });
    };
    ws.onmessage = (ev) => {
      let msg: RealtimeEvent;
      try {
        msg = JSON.parse(String(ev.data)) as RealtimeEvent;
      } catch {
        return;
      }
      const id = workspaceOf(msg);
      if (msg.type === "subscribed") this.confirmed.add(msg.workspace_id);
      if (msg.type === "revoked" || msg.type === "subscribe_failed") this.confirmed.delete(msg.workspace_id);
      if (id && this.handlers.has(id)) this.handlers.get(id)!.forEach((h) => h(msg));
      if (!id || msg.type === "access_changed" || msg.type === "session_ended") {
        this.handlers.forEach((set) => set.forEach((h) => h(msg)));
      }
    };
    ws.onclose = (ev) => {
      this.ws = null;
      this.confirmed.clear();
      if (this.stopped) return;
      if (ev.code === 4401) {
        this.setState("offline");
        return;
      }
      this.retry += 1;
      this.setState("reconnecting");
      const delay = Math.min(15000, 500 * 2 ** Math.min(this.retry, 5));
      this.timer = window.setTimeout(() => this.open(), delay);
    };
  }

  send(msg: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }

  subscribe(workspaceId: string, handler: Handler): () => void {
    let set = this.handlers.get(workspaceId);
    if (!set) {
      set = new Set();
      this.handlers.set(workspaceId, set);
      this.send({ type: "subscribe", workspace_id: workspaceId });
    }
    set.add(handler);
    if (this.confirmed.has(workspaceId)) {
      // Late subscriber: let it catch up from committed state now.
      queueMicrotask(() => handler({ type: "subscribed", workspace_id: workspaceId }));
    }
    return () => {
      const s = this.handlers.get(workspaceId);
      if (!s) return;
      s.delete(handler);
      if (s.size === 0) {
        this.handlers.delete(workspaceId);
        this.confirmed.delete(workspaceId);
        this.send({ type: "unsubscribe", workspace_id: workspaceId });
      }
    };
  }
}

export const realtime = new Realtime();
