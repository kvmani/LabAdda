// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { lazy } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { PageChunk } from "./PageChunk";

afterEach(cleanup);

it("shows a loading state, then the page", async () => {
  const Page = lazy(() => Promise.resolve({ default: () => <p>Calendar ready</p> }));
  render(
    <PageChunk label="Loading the calendar">
      <Page />
    </PageChunk>,
  );
  expect(screen.getByText("Loading the calendar")).toBeTruthy();
  expect(await screen.findByText("Calendar ready")).toBeTruthy();
});

it("offers a reload when the page's code cannot be downloaded", async () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  const Broken = lazy(() => Promise.reject(new Error("Failed to fetch dynamically imported module")));
  render(
    <PageChunk label="Loading the calendar">
      <Broken />
    </PageChunk>,
  );
  expect(await screen.findByText("This page could not be loaded")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Reload this page" })).toBeTruthy();
});
