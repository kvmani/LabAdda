import { mkdtemp, readFile, writeFile, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { buildHelp, compileHelp, HelpBuildError } from "./build-help.mjs";

const FRONT =
  "---\ntitle: Test page\nsummary: A page for tests.\naudience: everyone\nscreen: /today\nupdated: 2026-11-11\n---\n";
const page = (body, front = FRONT) => ({ "using/test.md": front + body });

describe("compileHelp", () => {
  it("indexes a page with its shelf, route and headings", () => {
    const { entries } = compileHelp(page("## What this is for\n\nText.\n\n## Extra topic\n\nMore.\n"));
    expect(entries).toEqual([
      {
        slug: "using/test",
        shelf: "using",
        title: "Test page",
        summary: "A page for tests.",
        audience: "everyone",
        screen: "/today",
        updated: "2026-11-11",
        headings: ["Extra topic"],
      },
    ]);
  });

  it("does not render raw HTML or script from a help file", () => {
    const body =
      '<script>alert("x")</script>\n\nText <img src="x" onerror="alert(1)"> end\n\n<div onclick="x()">block</div>\n';
    const { pages } = compileHelp(page(body));
    const html = pages["using/test"];
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<div");
    expect(html).toContain("&lt;script&gt;");
  });

  it("drops images instead of requesting them", () => {
    const { pages } = compileHelp(page("![Chart](https://example.invalid/a.png)\n"));
    expect(pages["using/test"]).not.toContain("<img");
  });

  it("rejects links that leave the help centre", () => {
    for (const href of ["https://example.invalid", "javascript:alert(1)", "#top", "/admin"]) {
      expect(() => compileHelp(page(`[x](${href})\n`))).toThrow(HelpBuildError);
    }
  });

  it("rejects a link to a page that does not exist and rewrites one that does", () => {
    expect(() => compileHelp(page("[x](missing.md)\n"))).toThrow(/broken link/);
    const sources = { ...page("[other](other.md)\n"), "using/other.md": FRONT };
    expect(compileHelp(sources).pages["using/test"]).toContain('href="help/using/other"');
  });

  it("rejects missing or invalid front matter", () => {
    expect(() => compileHelp({ "a.md": "No front matter" })).toThrow(/front matter block/);
    const missing = FRONT.replace("summary: A page for tests.\n", "");
    expect(() => compileHelp(page("x", missing))).toThrow(/needs "summary"/);
    expect(() => compileHelp(page("x", FRONT.replace("everyone", "visitors")))).toThrow(/audience/);
    expect(() => compileHelp(page("x", FRONT.replace("/today", "today")))).toThrow(/screen/);
    expect(() => compileHelp(page("x", FRONT.replace("2026-11-11", "yesterday")))).toThrow(/updated/);
  });
});

describe("buildHelp", () => {
  it("writes the index, one module per page and a loader table", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "help-"));
    await mkdir(path.join(root, "src/using"), { recursive: true });
    await writeFile(path.join(root, "src/using/test.md"), FRONT + "## What this is for\n\nText.\n");
    const count = await buildHelp(path.join(root, "src"), path.join(root, "out"));
    expect(count).toBe(1);
    expect(JSON.parse(await readFile(path.join(root, "out/index.json"), "utf8"))).toHaveLength(1);
    expect(await readFile(path.join(root, "out/loaders.ts"), "utf8")).toContain("using--test");
    expect(await readFile(path.join(root, "out/pages/using--test.ts"), "utf8")).toContain("What this is for");
  });
});
