import { afterEach, expect, it } from "vitest";
import { boardDraft, clearBoardDraft, rememberBoard } from "./draft";

afterEach(() => clearBoardDraft());
it("keeps drafts in the current session and rejects another identity", () => {
  rememberBoard({ key: "asha:session1", document: { revision: 2, objects: [] }, objects: [] });
  expect(boardDraft("asha:session1")?.document.revision).toBe(2);
  expect(boardDraft("ben:session2")).toBeNull();
  expect(boardDraft("asha:session1")).toBeNull();
});
it("an old identity cannot clear a newer identity's draft", () => {
  rememberBoard({ key: "ben:new", document: { revision: 0, objects: [] }, objects: [] });
  clearBoardDraft("asha:old");
  expect(boardDraft("ben:new")).not.toBeNull();
  clearBoardDraft();
  expect(boardDraft("ben:new")).toBeNull();
});
