// Compiles the in-app help centre (HP-01): reads frontend/src/help/**/*.md, validates front matter,
// renders safe HTML and writes an index plus one lazily loaded module per page into
// src/features/help/generated/ (git-ignored). Run by `npm run build` and `npm run dev`.
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Marked } from "marked";

const FRONT_MATTER_KEYS = ["title", "summary", "audience", "screen", "updated"];
const AUDIENCES = ["everyone", "steward", "administrator", "operator"];
const SHELF_FOLDERS = ["using", "stewards", "admin", "operator", "troubleshooting"];
// Every page repeats these headings, so searching them would match everything.
const TEMPLATE_HEADINGS = [
  "What this is for",
  "Before you start",
  "Steps",
  "What happens next",
  "If something goes wrong",
  "Related",
];
const SCHEME = /^[a-zA-Z][a-zA-Z0-9+.-]*:/;

export class HelpBuildError extends Error {}

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function plainText(html) {
  return html
    .replace(/<[^>]*>/g, "")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function headingId(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Splits `---` front matter from the body and checks every key and value. */
export function parseFrontMatter(source, file) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(source);
  if (!match) throw new HelpBuildError(`${file}: the page must start with a front matter block`);
  const data = {};
  for (const line of match[1].split(/\r?\n/)) {
    const pair = /^([a-z]+):\s*(.*?)\s*$/.exec(line);
    if (!pair) throw new HelpBuildError(`${file}: cannot read front matter line "${line}"`);
    const value = pair[2].replace(/^"(.*)"$/, "$1");
    if (!FRONT_MATTER_KEYS.includes(pair[1])) {
      throw new HelpBuildError(`${file}: unknown front matter key "${pair[1]}"`);
    }
    data[pair[1]] = value;
  }
  for (const key of FRONT_MATTER_KEYS) {
    if (!data[key]) throw new HelpBuildError(`${file}: front matter needs "${key}"`);
  }
  if (!AUDIENCES.includes(data.audience)) {
    throw new HelpBuildError(`${file}: audience must be one of ${AUDIENCES.join(", ")}`);
  }
  if (data.screen !== "none" && !data.screen.startsWith("/")) {
    throw new HelpBuildError(`${file}: screen must be a route starting with "/" or "none"`);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(data.updated)) {
    throw new HelpBuildError(`${file}: updated must be a date like 2026-11-11`);
  }
  return { data, body: match[2] };
}

/** Renders Markdown with raw HTML escaped, images dropped and only in-help links kept. */
export function renderMarkdown(body, file, knownSlugs) {
  const headings = [];
  const directory = path.posix.dirname(file);
  const renderer = {
    html: ({ text }) => escapeHtml(text),
    image: ({ text }) => escapeHtml(text),
    heading({ tokens, depth }) {
      const html = this.parser.parseInline(tokens);
      const text = plainText(html);
      if ((depth === 2 || depth === 3) && !TEMPLATE_HEADINGS.includes(text)) headings.push(text);
      return `<h${depth} id="${headingId(text)}">${html}</h${depth}>\n`;
    },
    link({ href, tokens }) {
      const label = this.parser.parseInline(tokens);
      if (SCHEME.test(href) || href.startsWith("#") || href.startsWith("/") || !href.endsWith(".md")) {
        throw new HelpBuildError(`${file}: links must point at another help page (.md), not "${href}"`);
      }
      const slug = path.posix.normalize(path.posix.join(directory, href)).replace(/\.md$/, "");
      if (!knownSlugs.has(slug)) throw new HelpBuildError(`${file}: broken link to "${href}"`);
      return `<a href="help/${slug}" data-help-page="${slug}">${label}</a>`;
    },
  };
  const html = new Marked({ renderer, gfm: true }).parse(body);
  return { html, headings };
}

async function markdownFiles(directory, prefix = "") {
  const found = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) found.push(...(await markdownFiles(path.join(directory, entry.name), relative)));
    else if (entry.name.endsWith(".md")) found.push(relative);
  }
  return found.sort();
}

function shelfOf(slug) {
  const folder = slug.split("/")[0];
  return SHELF_FOLDERS.includes(folder) && slug.includes("/") ? folder : "reference";
}

/** Returns the index entries and page modules for the given {file: source} map. */
export function compileHelp(sources) {
  const slugs = new Set(Object.keys(sources).map((file) => file.replace(/\.md$/, "")));
  const entries = [];
  const pages = {};
  for (const [file, source] of Object.entries(sources)) {
    const slug = file.replace(/\.md$/, "");
    const { data, body } = parseFrontMatter(source, file);
    const { html, headings } = renderMarkdown(body, file, slugs);
    entries.push({
      slug,
      shelf: shelfOf(slug),
      title: data.title,
      summary: data.summary,
      audience: data.audience,
      screen: data.screen === "none" ? null : data.screen,
      updated: data.updated,
      headings,
    });
    pages[slug] = html;
  }
  entries.sort((a, b) => a.title.localeCompare(b.title));
  return { entries, pages };
}

function moduleName(slug) {
  return slug.replace(/\//g, "--");
}

export async function buildHelp(sourceDirectory, outputDirectory) {
  const files = await markdownFiles(sourceDirectory);
  const sources = {};
  for (const file of files) sources[file] = await readFile(path.join(sourceDirectory, file), "utf8");
  const { entries, pages } = compileHelp(sources);
  await rm(outputDirectory, { recursive: true, force: true });
  await mkdir(path.join(outputDirectory, "pages"), { recursive: true });
  await writeFile(path.join(outputDirectory, "index.json"), JSON.stringify(entries, null, 2) + "\n");
  const loaders = [];
  for (const slug of Object.keys(pages)) {
    const body = `export default ${JSON.stringify(pages[slug])};\n`;
    await writeFile(path.join(outputDirectory, "pages", `${moduleName(slug)}.ts`), body);
    loaders.push(`  "${slug}": () => import("./pages/${moduleName(slug)}"),`);
  }
  const header = "// Generated by scripts/build-help.mjs. Do not edit.\n";
  const type = "export const pageLoaders: Record<string, () => Promise<{ default: string }>> = {\n";
  await writeFile(path.join(outputDirectory, "loaders.ts"), `${header}${type}${loaders.join("\n")}\n};\n`);
  return entries.length;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  try {
    const count = await buildHelp(
      path.join(root, "src/help"),
      path.join(root, "src/features/help/generated"),
    );
    console.log(`build-help: ${count} page(s)`);
  } catch (error) {
    if (!(error instanceof HelpBuildError)) throw error;
    console.error(`build-help: ${error.message}`);
    process.exit(1);
  }
}
