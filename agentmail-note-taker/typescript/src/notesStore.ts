/**
 * Markdown-with-frontmatter notes store.
 *
 * Each note is a single Markdown file in `notes/<YYYY-MM-DD>-<slug>.md` with
 * YAML frontmatter. The file is the source of truth — re-read on every search.
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";

const NOTES_DIR = "notes";

function slugify(text: string, maxLen = 40): string {
  return text.toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, maxLen) || "note";
}

function yamlFrontmatter(meta: Record<string, any>): string {
  const lines = ["---"];
  for (const [k, v] of Object.entries(meta)) {
    if (Array.isArray(v)) {
      lines.push(`${k}: [${v.join(", ")}]`);
    } else {
      const sv = String(v).replace(/"/g, '\\"');
      if (/[:,#\[\]]/.test(sv)) lines.push(`${k}: "${sv}"`);
      else lines.push(`${k}: ${sv}`);
    }
  }
  lines.push("---");
  return lines.join("\n");
}

export function findByThread(threadId: string): string | null {
  if (!existsSync(NOTES_DIR) || !threadId) return null;
  for (const fn of readdirSync(NOTES_DIR)) {
    if (!fn.endsWith(".md")) continue;
    const path = join(NOTES_DIR, fn);
    try {
      const head = readFileSync(path, "utf-8").slice(0, 2000);
      if (head.includes(`thread_id: ${threadId}`) || head.includes(`thread_id: "${threadId}"`)) {
        return path;
      }
    } catch { /* skip */ }
  }
  return null;
}

export interface NoteInput {
  sourceSummary: string;
  threadId: string;
  tags: string[];
  summary: string;
  decisions: string[];
  actionItems: Array<{ owner?: string; task?: string; deadline?: string; urgency?: string }>;
  openQuestions: string[];
  keyFacts: string[];
  existingPath?: string | null;
}

export function writeNote(input: NoteInput): string {
  if (!existsSync(NOTES_DIR)) mkdirSync(NOTES_DIR, { recursive: true });
  const today = new Date().toISOString().slice(0, 10);

  let path: string;
  if (input.existingPath && existsSync(input.existingPath)) {
    path = input.existingPath;
  } else {
    const slugSeed = ((input.tags[0] || "") + " " + input.summary.slice(0, 40));
    let candidate = join(NOTES_DIR, `${today}-${slugify(slugSeed)}.md`);
    let i = 1;
    while (existsSync(candidate)) {
      candidate = join(NOTES_DIR, `${today}-${slugify(slugSeed)}-${i}.md`);
      i++;
    }
    path = candidate;
  }

  const meta = {
    source: input.sourceSummary,
    date: today,
    thread_id: input.threadId || "",
    tags: input.tags,
  };

  const lines: string[] = [yamlFrontmatter(meta), "", `# Summary`, "", input.summary, ""];

  if (input.decisions.length) {
    lines.push("## Decisions", "");
    for (const d of input.decisions) lines.push(`- ${d}`);
    lines.push("");
  }
  if (input.actionItems.length) {
    lines.push("## Action items", "");
    for (const ai of input.actionItems) {
      const owner = ai.owner || "(unassigned)";
      const task = ai.task || "";
      const tail = [ai.deadline, ai.urgency].filter(Boolean).join(" · ");
      const tailStr = tail ? `  (${tail})` : "";
      lines.push(`- **${owner}**: ${task}${tailStr}`);
    }
    lines.push("");
  }
  if (input.openQuestions.length) {
    lines.push("## Open questions", "");
    for (const q of input.openQuestions) lines.push(`- ${q}`);
    lines.push("");
  }
  if (input.keyFacts.length) {
    lines.push("## Key facts", "");
    for (const f of input.keyFacts) lines.push(`- ${f}`);
    lines.push("");
  }

  writeFileSync(path, lines.join("\n"), "utf-8");
  return path;
}

export interface NoteMeta {
  path: string;
  date: string;
  tags: string[];
  threadId: string;
  source: string;
  summary: string;
}

export function parseFrontmatter(text: string): Record<string, any> {
  if (!text.startsWith("---")) return {};
  const end = text.indexOf("\n---", 3);
  if (end === -1) return {};
  const block = text.slice(3, end);
  const out: Record<string, any> = {};
  for (const line of block.trim().split("\n")) {
    if (!line.includes(":")) continue;
    const [k, ...rest] = line.split(":");
    const v = rest.join(":").trim();
    if (v.startsWith("[") && v.endsWith("]")) {
      out[k.trim()] = v.slice(1, -1).split(",").map(x => x.trim().replace(/^"|"$/g, "")).filter(Boolean);
    } else if (v.startsWith('"') && v.endsWith('"')) {
      out[k.trim()] = v.slice(1, -1);
    } else {
      out[k.trim()] = v;
    }
  }
  return out;
}

export function listAll(): NoteMeta[] {
  if (!existsSync(NOTES_DIR)) return [];
  const files = readdirSync(NOTES_DIR).filter(f => f.endsWith(".md")).sort().reverse();
  const items: NoteMeta[] = [];
  for (const fn of files) {
    const path = join(NOTES_DIR, fn);
    let text: string;
    try { text = readFileSync(path, "utf-8"); } catch { continue; }
    const meta = parseFrontmatter(text);
    let summary = "";
    const afterFm = text.split("---", 3).slice(2).join("---") || text;
    const m = afterFm.match(/# Summary\n+([\s\S]+?)(?:\n\n|\n#)/);
    if (m) summary = m[1].trim().replace(/\n/g, " ");
    items.push({
      path, date: meta.date || "", tags: meta.tags || [],
      threadId: meta.thread_id || "", source: meta.source || "", summary,
    });
  }
  return items;
}

export function search(query: string, limit = 10): NoteMeta[] {
  const items = listAll();
  if (!items.length) return [];
  const qTerms = query.toLowerCase().split(/\W+/).filter(t => t.length > 2);
  const scored: Array<[number, NoteMeta]> = [];
  for (const item of items) {
    const text = (item.summary + " " + item.tags.join(" ") + " " + item.source).toLowerCase();
    let body = "";
    try { body = readFileSync(item.path, "utf-8").toLowerCase(); } catch {}
    let score = 0;
    for (const t of qTerms) {
      score += (text.match(new RegExp(t, "g")) || []).length * 3
             + (body.match(new RegExp(t, "g")) || []).length;
      if (item.tags.includes(t)) score += 5;
    }
    if (score > 0) scored.push([score, item]);
  }
  scored.sort((a, b) => b[0] - a[0]);
  return scored.slice(0, limit).map(([_, item]) => item);
}

export function readNoteExcerpt(path: string, maxChars = 1500): string {
  if (!existsSync(path)) return "";
  let text = readFileSync(path, "utf-8");
  if (text.startsWith("---")) {
    const end = text.indexOf("\n---", 3);
    if (end !== -1) text = text.slice(end + 4).replace(/^\s+/, "");
  }
  return text.slice(0, maxChars);
}
