import { useEffect, useState } from "react";
import { api } from "../../api";

export type SiteBanner = { message: string; level: "info" | "warning" };

/** Check this often; the server alone decides whether the notice window contains now. */
const POLL_MILLISECONDS = 60_000;

/** The notice to show above every page, or null. A failed check simply shows nothing. */
export function useSiteBanner(): SiteBanner | null {
  const [banner, setBanner] = useState<SiteBanner | null>(null);
  useEffect(() => {
    let live = true;
    const load = () =>
      api<{ banner: SiteBanner | null }>("/site/banner")
        .then((result) => {
          if (live) setBanner(result.banner);
        })
        .catch(() => undefined);
    void load();
    const timer = window.setInterval(() => void load(), POLL_MILLISECONDS);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, []);
  return banner;
}
