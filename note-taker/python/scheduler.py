"""
Scheduler: 24h-before-deadline reminders + Friday weekly digest.

Runs once per agent loop iteration. Dedupes via .notifications.json so
reminders don't fire twice for the same action.
"""

import json
from datetime import datetime
from pathlib import Path

import actions as actions_mod

NOTIFICATIONS_FILE = Path(".notifications.json")
DIGEST_STATE = Path(".last_digest")


def _load_notif_state() -> dict:
    if NOTIFICATIONS_FILE.exists():
        try:
            return json.loads(NOTIFICATIONS_FILE.read_text())
        except Exception:
            pass
    return {"reminded": []}


def _save_notif_state(state: dict) -> None:
    NOTIFICATIONS_FILE.write_text(json.dumps(state, indent=2))


# --- 24h reminders ------------------------------------------------------------


def _reminder_email_body(action: dict, recipient_label: str) -> str:
    return (
        f"Hi {recipient_label},\n\n"
        f"Heads-up: an open action item is coming due.\n\n"
        f"  Task:     {action['task']}\n"
        f"  Owner:    {action['owner'] or '(unassigned)'}\n"
        f"  Deadline: {action['deadline']}\n"
        f"  Urgency:  {action['urgency']}\n\n"
        f"From note: {action['note_path']}\n\n"
        f"— Notes assistant"
    )


def fire_due_reminders(*, agentmail_client, inbox, user_email: str,
                       reminder_hours: float, notify_assignees: bool) -> None:
    """For each open action whose deadline is within `reminder_hours`,
    send a single reminder. Skip if already reminded."""
    state = _load_notif_state()
    reminded = set(state.get("reminded", []))
    now = datetime.now()

    sent_any = False
    for action in actions_mod.list_open():
        hrs = actions_mod.hours_until(action, now)
        if hrs is None or hrs > reminder_hours or hrs < -1:
            # No deadline, too far out, or already > 1h overdue (skip — digest covers overdue)
            continue
        aid = action["id"]
        if aid in reminded:
            continue

        # Always email the user
        try:
            agentmail_client.inboxes.messages.send(
                inbox.inbox_id,
                to=[user_email],
                subject=f"[Reminder] Due soon: {action['task'][:60]}",
                text=_reminder_email_body(action, "you"),
            )
            sent_any = True
            print(f"  ✓ reminded user about action {aid}: {action['task'][:50]}")
        except Exception as e:
            print(f"  ! reminder send failed: {e}")
            continue

        # Optionally also email the assignee directly
        if notify_assignees and "@" in (action.get("owner") or ""):
            try:
                agentmail_client.inboxes.messages.send(
                    inbox.inbox_id,
                    to=[action["owner"]],
                    subject=f"[Reminder] Due soon: {action['task'][:60]}",
                    text=_reminder_email_body(action, action["owner"].split("@")[0]),
                )
                print(f"  ✓ reminded assignee {action['owner']}")
            except Exception as e:
                print(f"  ! assignee reminder failed: {e}")

        reminded.add(aid)

    if sent_any:
        state["reminded"] = sorted(reminded)
        _save_notif_state(state)


# --- Friday weekly digest -----------------------------------------------------


def _digest_body(open_actions: list[dict], now: datetime) -> str:
    if not open_actions:
        return "No open action items this week. Inbox zero applies to your task list too 🎉\n\n— Notes assistant"

    overdue = [a for a in open_actions if actions_mod.is_overdue(a, now)]
    high = [a for a in open_actions if a["urgency"] == "high" and a not in overdue]
    rest = [a for a in open_actions if a not in overdue and a not in high]

    lines = [
        f"Weekly digest — {now.strftime('%a %b %d')}",
        "",
        f"Open actions: {len(open_actions)}   "
        f"Overdue: {len(overdue)}   High urgency: {len(high)}   Other: {len(rest)}",
    ]

    def fmt_section(title: str, rows: list[dict]) -> list[str]:
        if not rows:
            return []
        out = ["", f"{title}:"]
        for r in rows:
            owner = r.get("owner") or "(unassigned)"
            deadline = r.get("deadline") or "no deadline"
            out.append(f"  • [{owner}] {r['task']} (due {deadline})")
            out.append(f"     from {r['note_path']}")
        return out

    lines += fmt_section("OVERDUE", overdue)
    lines += fmt_section("HIGH URGENCY", high)
    lines += fmt_section("OTHER OPEN", rest)
    lines += ["", "— Notes assistant"]
    return "\n".join(lines)


def maybe_send_digest(*, agentmail_client, inbox, user_email: str,
                      hour: int, weekday: int) -> None:
    """If today is the configured weekday and time is past `hour`, send the digest."""
    if weekday < 0:  # disabled
        return
    now = datetime.now()
    if now.weekday() != weekday or now.hour < hour:
        return
    today_str = now.strftime("%Y-%m-%d")
    if DIGEST_STATE.exists() and DIGEST_STATE.read_text().strip() == today_str:
        return

    open_actions = actions_mod.list_open()
    body = _digest_body(open_actions, now)
    try:
        agentmail_client.inboxes.messages.send(
            inbox.inbox_id,
            to=[user_email],
            subject=f"Weekly notes digest — {now.strftime('%b %d')}",
            text=body,
        )
        DIGEST_STATE.write_text(today_str)
        print(f"  ✓ sent weekly digest to {user_email} ({len(open_actions)} open actions)")
    except Exception as e:
        print(f"  ! digest send failed: {e}")
