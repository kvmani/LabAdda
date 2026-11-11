import type { MutableRefObject } from "react";

/**
 * Discard every response still in flight for this counter.
 *
 * Components number each request with a generation counter and ignore a response whose number
 * is no longer current, so a slow reply cannot show data after the scope changed or access was
 * revoked. Effect cleanups call this to advance the live counter; copying the ref first, as the
 * hooks lint rule suggests for DOM refs, would defeat the purpose.
 */
export function invalidate(counter: MutableRefObject<number>): void {
  counter.current += 1;
}
