import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button, Drawer, type HelpEntryProps } from "../../ui";
import { HelpArticle } from "./HelpArticle";
import { loadHelpIndex } from "./content";
import { entryForRoute } from "./screens";
import { useLoaded } from "./useLoaded";

/** The "Help with this page" control in every page header: opens the matching page beside the work. */
export function HelpLink({ fallback }: HelpEntryProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { state } = useLoaded(loadHelpIndex, "index");
  const [open, setOpen] = useState(false);
  const entry = state.status === "ready" ? entryForRoute(state.value, pathname) : null;
  if (!entry) return <>{fallback}</>;

  function openPage(slug: string) {
    setOpen(false);
    navigate(`/help/${slug}`);
  }

  return (
    <>
      <Button variant="quiet" size="sm" icon="help" onClick={() => setOpen(true)} aria-haspopup="dialog">
        Help with this page
      </Button>
      <Drawer
        open={open}
        title={entry.title}
        onClose={() => setOpen(false)}
        footer={<Button onClick={() => openPage(entry.slug)}>Open the full guide</Button>}
      >
        <HelpArticle slug={entry.slug} onOpenPage={openPage} />
      </Drawer>
    </>
  );
}
