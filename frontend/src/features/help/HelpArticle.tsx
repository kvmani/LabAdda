import { useEffect, useRef } from "react";
import { ErrorState, Skeleton } from "../../ui";
import { loadHelpPage } from "./content";
import { useLoaded } from "./useLoaded";
import "./help.css";

type HelpArticleProps = {
  slug: string;
  /** Called when a link inside the page points at another help page. */
  onOpenPage: (slug: string) => void;
};

/** The body of one help page. The HTML is produced and escaped at build time, never by a user. */
export function HelpArticle({ slug, onOpenPage }: HelpArticleProps) {
  const { state, retry } = useLoaded(() => loadHelpPage(slug), slug);
  const container = useRef<HTMLDivElement>(null);
  const openPage = useRef(onOpenPage);
  openPage.current = onOpenPage;

  useEffect(() => {
    const element = container.current;
    if (!element) return undefined;
    // Real links keep working with the keyboard; this only avoids a full page load.
    const follow = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest("a[data-help-page]") : null;
      const page = target?.getAttribute("data-help-page");
      if (!page) return;
      event.preventDefault();
      openPage.current(page);
    };
    element.addEventListener("click", follow);
    return () => element.removeEventListener("click", follow);
  }, [state.status]);

  if (state.status === "loading") return <Skeleton lines={6} label="Loading this help page" />;
  if (state.status === "error") {
    return (
      <ErrorState
        title="This help page could not be loaded"
        message="Check your connection to the server and try again."
        onRetry={retry}
      />
    );
  }
  return <div ref={container} className="help-article" dangerouslySetInnerHTML={{ __html: state.value }} />;
}
