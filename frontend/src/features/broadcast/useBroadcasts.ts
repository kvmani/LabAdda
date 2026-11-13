import { useEffect, useState } from "react";
import { api } from "../../api";
import type { SiteMessage } from "./types";

/** Check this often; the server alone decides which messages are on screen now. */
const POLL_MILLISECONDS = 60_000;

/** The messages to show above every page. A failed check keeps what is already shown. */
export function useBroadcasts(): SiteMessage[] {
  const [messages, setMessages] = useState<SiteMessage[]>([]);
  useEffect(() => {
    let live = true;
    const load = () =>
      api<{ broadcasts: SiteMessage[] }>("/site/broadcasts")
        .then((result) => {
          if (live) setMessages(result.broadcasts);
        })
        .catch(() => undefined);
    void load();
    const timer = window.setInterval(() => void load(), POLL_MILLISECONDS);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, []);
  return messages;
}
