/**
 * 24h-before-deadline reminders + Friday weekly digest.
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import * as actions from "./actions.js";

const NOTIFICATIONS_FILE = ".notifications.json";
const DIGEST_STATE = ".last_digest";

function loadNotifState(): { reminded: string[] } {
  if (!existsSync(NOTIFICATIONS_FILE)) return { reminded: [] };
  try { return JSON.parse(readFileSync(NOTIFICATIONS_FILE, "utf-8")); }
  catch { return { reminded: [] }; }
}

function saveNotifState(state: { reminded: string[] }): void {
  writeFileSync(NOTIFICATIONS_FILE, JSON.stringify(state, null, 2));
}

function reminderBody(action: actions.ActionRow, recipient: string): string {
  return (
    `Hi ${recipient},\n\n` +
    `Heads-up: an open action item is coming due.\n\n` +
    `  Task:     ${action.task}\n` +
    `  Owner:    ${action.owner || "(unassigned)"}\n` +
    `  Deadline: ${action.deadline}\n` +
    `  Urgency:  ${action.urgency}\n\n` +
    `From note: ${action.note_path}\n\n` +
    `— Notes assistant`
  );
}

export async function fireDueReminders(opts: {
  agentmail: any;
  inbox: any;
  userEmail: string;
  reminderHours: number;
  notifyAssignees: boolean;
}): Promise<void> {
  const state = loadNotifState();
  const reminded = new Set(state.reminded);
  const now = new Date();
  let sentAny = false;

  for (const action of actions.listOpen()) {
    const hrs = actions.hoursUntil(action, now);
    if (hrs === null || hrs > opts.reminderHours || hrs < -1) continue;
    if (reminded.has(action.id)) continue;

    try {
      await opts.agentmail.inboxes.messages.send(opts.inbox.inboxId, {
        to: [opts.userEmail],
        subject: `[Reminder] Due soon: ${action.task.slice(0, 60)}`,
        text: reminderBody(action, "you"),
      });
      sentAny = true;
      console.log(`  ✓ reminded user about action ${action.id}: ${action.task.slice(0, 50)}`);
    } catch (e: any) {
      console.warn(`  ! reminder send failed: ${e.message}`);
      continue;
    }

    if (opts.notifyAssignees && (action.owner || "").includes("@")) {
      try {
        await opts.agentmail.inboxes.messages.send(opts.inbox.inboxId, {
          to: [action.owner],
          subject: `[Reminder] Due soon: ${action.task.slice(0, 60)}`,
          text: reminderBody(action, action.owner.split("@")[0]),
        });
        console.log(`  ✓ reminded assignee ${action.owner}`);
      } catch (e: any) {
        console.warn(`  ! assignee reminder failed: ${e.message}`);
      }
    }

    reminded.add(action.id);
  }

  if (sentAny) {
    state.reminded = Array.from(reminded).sort();
    saveNotifState(state);
  }
}

function digestBody(openActions: actions.ActionRow[], now: Date): string {
  if (!openActions.length) {
    return "No open action items this week. Inbox zero applies to your task list too 🎉\n\n— Notes assistant";
  }

  const overdue = openActions.filter(a => actions.isOverdue(a, now));
  const high = openActions.filter(a => a.urgency === "high" && !overdue.includes(a));
  const rest = openActions.filter(a => !overdue.includes(a) && !high.includes(a));

  const lines = [
    `Weekly digest — ${now.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}`,
    "",
    `Open actions: ${openActions.length}   Overdue: ${overdue.length}   ` +
    `High urgency: ${high.length}   Other: ${rest.length}`,
  ];

  function fmtSection(title: string, rows: actions.ActionRow[]): string[] {
    if (!rows.length) return [];
    const out = ["", `${title}:`];
    for (const r of rows) {
      const owner = r.owner || "(unassigned)";
      const deadline = r.deadline || "no deadline";
      out.push(`  • [${owner}] ${r.task} (due ${deadline})`);
      out.push(`     from ${r.note_path}`);
    }
    return out;
  }

  lines.push(...fmtSection("OVERDUE", overdue));
  lines.push(...fmtSection("HIGH URGENCY", high));
  lines.push(...fmtSection("OTHER OPEN", rest));
  lines.push("", "— Notes assistant");
  return lines.join("\n");
}

export async function maybeSendDigest(opts: {
  agentmail: any;
  inbox: any;
  userEmail: string;
  hour: number;
  weekday: number;
}): Promise<void> {
  if (opts.weekday < 0) return;  // disabled
  const now = new Date();
  // JS getDay(): Sun=0..Sat=6. Config uses Python convention Mon=0..Sun=6.
  const pyWeekday = (now.getDay() + 6) % 7;
  if (pyWeekday !== opts.weekday) return;
  if (now.getHours() < opts.hour) return;

  const todayStr = now.toISOString().slice(0, 10);
  if (existsSync(DIGEST_STATE) && readFileSync(DIGEST_STATE, "utf-8").trim() === todayStr) return;

  const openActions = actions.listOpen();
  const body = digestBody(openActions, now);
  try {
    await opts.agentmail.inboxes.messages.send(opts.inbox.inboxId, {
      to: [opts.userEmail],
      subject: `Weekly notes digest — ${now.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`,
      text: body,
    });
    writeFileSync(DIGEST_STATE, todayStr);
    console.log(`  ✓ sent weekly digest to ${opts.userEmail} (${openActions.length} open actions)`);
  } catch (e: any) {
    console.warn(`  ! digest send failed: ${e.message}`);
  }
}
