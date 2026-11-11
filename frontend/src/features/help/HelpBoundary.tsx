import { Component, type ReactNode } from "react";
import { ErrorState } from "../../ui";

/** A help chunk that fails to load must leave the rest of the application usable. */
export class HelpBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  override state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  override render() {
    if (this.state.failed) {
      return (
        <ErrorState
          title="Help could not be loaded"
          message="Check your connection to the server, then reload this page. Your work is not affected."
          retryLabel="Reload help"
          onRetry={() => window.location.reload()}
        />
      );
    }
    return this.props.children;
  }
}
