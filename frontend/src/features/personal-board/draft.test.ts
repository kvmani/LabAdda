import { afterEach, expect, it } from "vitest";
import { boardDraft, clearBoardDraft, clearSavedBoard, rememberBoard } from "./draft";

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

it("keeps independent drafts for each board in the same session", () => {
  rememberBoard({ key: "asha:session1:0", document: { revision: 2, objects: [] }, objects: [] });
  rememberBoard({ key: "asha:session1:1", document: { revision: 3, objects: [] }, objects: [] });
  expect(boardDraft("asha:session1:0")?.document.revision).toBe(2);
  expect(boardDraft("asha:session1:1")?.document.revision).toBe(3);
  clearBoardDraft("asha:session1:0");
  expect(boardDraft("asha:session1:1")?.document.revision).toBe(3);
});

it("a late save cannot erase another identity's draft or a newer edit", () => {
  const oldObjects: never[] = [];
  rememberBoard({ key: "bharat:new:0", document: { revision: 1, objects: [] }, objects: [] });
  clearSavedBoard("asha:old:0", oldObjects);
  expect(boardDraft("bharat:new:0")).not.toBeNull();
  clearSavedBoard("bharat:new:0", oldObjects);
  expect(boardDraft("bharat:new:0")).not.toBeNull();
});
