import { describe, expect, it } from "vitest";
import { missedEventGate } from "./realtime";

describe("missedEventGate", () => {
  it("ignores the first subscription confirmation and flags reconnects", () => {
    const gate = missedEventGate();
    expect(gate({ type: "subscribed", workspace_id: "a" })).toBe(false);
    expect(gate({ type: "subscribed", workspace_id: "b" })).toBe(false);
    expect(gate({ type: "subscribed", workspace_id: "a" })).toBe(true);
    expect(gate({ type: "pong" })).toBe(false);
  });
});
