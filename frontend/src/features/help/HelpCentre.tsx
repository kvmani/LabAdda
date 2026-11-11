import { Route, Routes } from "react-router-dom";
import { ErrorState, Skeleton } from "../../ui";
import { loadHelpIndex } from "./content";
import { HelpHome } from "./HelpHome";
import { HelpPageView } from "./HelpPageView";
import { useLoaded } from "./useLoaded";

/** The /help area: home page and one page per guide. Loaded as its own chunk (HP-01). */
export function HelpCentre() {
  const { state, retry } = useLoaded(loadHelpIndex, "index");
  if (state.status === "loading") return <Skeleton lines={6} label="Loading help" />;
  if (state.status === "error") {
    return (
      <ErrorState
        title="Help could not be loaded"
        message="Check your connection to the server and try again."
        onRetry={retry}
      />
    );
  }
  return (
    <Routes>
      <Route index element={<HelpHome entries={state.value} />} />
      <Route path="*" element={<HelpPageView entries={state.value} />} />
    </Routes>
  );
}
