import { afterEach, expect, it } from "vitest";
import { boardDraft, clearBoardDraft, rememberBoard } from "./draft";

afterEach(() => clearBoardDraft());
it("keeps drafts in the current session and rejects another identity", () => {
  rememberBoard({ key: "asha:session1", document: { revision: 2, objects: [] }, objects: [] });
  expect(boardDraft("asha:session1")?.document.revision).toBe(2);
  expect(boardDraft("bharat:session2")).toBeNull();
  expect(boardDraft("asha:session1")).toBeNull();
});
it("an old identity cannot clear a newer identity's draft", () => {
  rememberBoard({ key: "bharat:new", document: { revision: 0, objects: [] }, objects: [] });
  clearBoardDraft("asha:old");
  expect(boardDraft("bharat:new")).not.toBeNull();
  clearBoardDraft();
  expect(boardDraft("bharat:new")).toBeNull();
});
