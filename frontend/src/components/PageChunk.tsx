import { Component, Suspense, type ReactNode } from "react";
import { ErrorState, Skeleton } from "../ui";

type Props = { label: string; children: ReactNode };

/**
 * A page whose code is downloaded when first opened, so the first screen loads less. A download
 * that fails (offline, or a release replaced while the tab was open) leaves the rest of the
 * application usable and offers a reload; the boundary is keyed by route so moving on clears it.
 */
class ChunkBoundary extends Component<Props, { failed: boolean }> {
  override state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  override render() {
    if (this.state.failed) {
      return (
        <ErrorState
          title="This page could not be loaded"
          message="Check your connection to the server, then reload. Your other pages are still available."
          retryLabel="Reload this page"
          onRetry={() => window.location.reload()}
        />
      );
    }
    return <Suspense fallback={<Skeleton label={this.props.label} />}>{this.props.children}</Suspense>;
  }
}

export function PageChunk({ label, children }: Props) {
  return <ChunkBoundary label={label}>{children}</ChunkBoundary>;
}
