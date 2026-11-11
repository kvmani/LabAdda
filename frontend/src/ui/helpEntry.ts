import { createContext, type ComponentType, type ReactNode } from "react";

export type HelpEntryProps = {
  /** What to show when no help page explains the current screen. */
  fallback: ReactNode;
};

/**
 * Lets the application shell supply the contextual help control that every page header shows
 * (UX-08), so `ui/` does not depend on the help feature. Without a provider the header shows
 * only its plain `helpHref` link.
 */
export const HelpEntryContext = createContext<ComponentType<HelpEntryProps> | null>(null);
