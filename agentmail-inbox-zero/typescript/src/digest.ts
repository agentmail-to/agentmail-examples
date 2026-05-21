/**
 * Build and send the morning digest.
 *
 * Runs once per day from the polling loop in agent.ts. Lists every draft
 * created since the previous digest, plus anything flagged for human attention.
 */

export function buildDigestText(opts: {
  userName: string;
  inboxEmail: string;
  drafts: any[];
  flagged: any[];
}): string {
  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  const lines: string[] = [
    `Good morning ${opts.userName},`,
    "",
    `Here's what landed overnight in ${opts.inboxEmail}.`,
    "",
  ];

  if (opts.drafts.length) {
    lines.push(
      `📝 ${opts.drafts.length} DRAFT${opts.drafts.length === 1 ? "" : "S"} READY TO REVIEW`,
    );
    lines.push("");
    for (const d of opts.drafts) {
      const to = (d.to || []).join(", ") || "(no recipient)";
      const subject = d.subject || "(no subject)";
      const previewRaw = (d.preview || d.text || "").trim().replace(/\n/g, " ");
      const preview =
        previewRaw.length > 140 ? previewRaw.slice(0, 140) + "..." : previewRaw;
      lines.push(`  → To: ${to}`);
      lines.push(`    Subject: ${subject}`);
      lines.push(`    Preview: ${preview}`);
      lines.push("");
    }
  } else {
    lines.push("📝 No drafts to review.");
    lines.push("");
  }

  if (opts.flagged.length) {
    lines.push(
      `⚠️  ${opts.flagged.length} EMAIL${opts.flagged.length === 1 ? "" : "S"} FLAGGED FOR YOUR ATTENTION`,
    );
    lines.push("");
    for (const m of opts.flagged) {
      const sender = m.from || m.from_ || "";
      const subject = m.subject || "(no subject)";
      lines.push(`  → From: ${sender}`);
      lines.push(`    Subject: ${subject}`);
      lines.push("");
    }
  }

  if (!opts.drafts.length && !opts.flagged.length) {
    lines.push("Inbox is clean. Nothing requires your attention.");
    lines.push("");
  }

  lines.push("---");
  lines.push(
    `Digest generated ${today}. Open ${opts.inboxEmail} to review and send.`,
  );

  return lines.join("\n");
}

export function isDigestDue(
  wakeTimeStr: string,
  lastDigestDate: string | undefined,
): boolean {
  let wakeH = 8;
  let wakeM = 0;
  try {
    const [h, m] = wakeTimeStr.trim().split(":");
    wakeH = parseInt(h, 10);
    wakeM = parseInt(m, 10);
  } catch {
    /* fallback */
  }

  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10); // YYYY-MM-DD

  if (lastDigestDate === todayStr) return false;

  const nowH = now.getHours();
  const nowM = now.getMinutes();
  return nowH > wakeH || (nowH === wakeH && nowM >= wakeM);
}
