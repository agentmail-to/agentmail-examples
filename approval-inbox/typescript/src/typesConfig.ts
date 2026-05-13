/**
 * Loads approval_types.yaml. Re-loads on every call.
 */

import { existsSync, readFileSync } from "node:fs";
import { parse as parseYaml } from "yaml";

const FILE = "approval_types.yaml";

export interface ActionBlock {
  forward_to?: string;
  webhook?: string;
  reply_to_sender?: string;
}

export interface TypeConfig {
  type: string;
  description: string;
  classifier_hints: { senders?: string[]; keywords?: string[] };
  extract_fields: string[];
  approve: ActionBlock;
  decline: ActionBlock;
}

export function load(): TypeConfig[] {
  if (!existsSync(FILE)) return [];
  let data: any;
  try {
    data = parseYaml(readFileSync(FILE, "utf-8"));
  } catch (e: any) {
    console.warn(`  ! approval_types.yaml malformed: ${e.message}`);
    return [];
  }
  const out: TypeConfig[] = [];
  for (const entry of (data?.types ?? []) as any[]) {
    out.push({
      type: entry.type,
      description: entry.description ?? "",
      classifier_hints: entry.classifier_hints ?? {},
      extract_fields: entry.extract_fields ?? [],
      approve: entry.approve ?? {},
      decline: entry.decline ?? {},
    });
  }
  return out;
}

export function find(types: TypeConfig[], typeName: string): TypeConfig | null {
  return types.find(t => t.type === typeName) ?? null;
}

export function renderForPrompt(types: TypeConfig[]): string {
  if (!types.length) {
    return "(no request types configured — every email will be discarded)";
  }
  return types.map(t => {
    const senders = (t.classifier_hints.senders || []).join(", ") || "(no sender hints)";
    const keywords = (t.classifier_hints.keywords || []).join(", ") || "(no keyword hints)";
    const fields = t.extract_fields.join(", ") || "(no fields)";
    return (
      `## ${t.type}\n` +
      `  - description: ${t.description}\n` +
      `  - sender hints: ${senders}\n` +
      `  - keyword hints: ${keywords}\n` +
      `  - fields to extract: [${fields}]`
    );
  }).join("\n\n");
}
