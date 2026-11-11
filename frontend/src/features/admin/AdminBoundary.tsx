import { Component, type ReactNode } from "react";
import { ErrorState } from "../../ui";

/** A failed console chunk must leave workspace navigation and the rest of the app usable. */
export class AdminBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  override state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  override render() {
    if (this.state.failed) {
      return (
        <ErrorState
          title="Administration could not be loaded"
          message="Check your connection, then reload this page. Your other workspaces are still available."
          retryLabel="Reload administration"
          onRetry={() => window.location.reload()}
        />
      );
    }
    return this.props.children;
  }
}
