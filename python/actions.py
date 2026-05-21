"""
Side-effect actions that fire after the user decides on a request.

Supported per type config:
  forward_to:      email address — forwards the original email to this address
  webhook:         URL — POSTs the request JSON
  reply_to_sender: string template — reply to the original sender's thread
                   (supports {field_name} interpolation from the extracted fields)
"""

import json
import re
import urllib.error
import urllib.request


def _interpolate(template: str, fields: dict) -> str:
    """Replace {key} with fields[key], unbraced for missing keys."""
    def replace(m):
        key = m.group(1)
        return str(fields.get(key, "")) or "(unspecified)"
    return re.sub(r"\{(\w+)\}", replace, template)


def _post_webhook(url: str, payload: dict) -> bool:
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        return True
    except Exception as e:
        print(f"  ! webhook failed: {e}")
        return False


def fire(*, agentmail_client, inbox, request_row: dict, type_config,
         decision: str, decision_args: dict | None = None) -> list[str]:
    """Run the configured side-effect actions for the decision.
    Returns a list of human-readable confirmations to include in the user ack."""
    actions_block = type_config.approve if decision == "approve" else type_config.decline
    fields = json.loads(request_row.get("fields_json", "{}") or "{}")
    confirmations: list[str] = []

    # 1. forward_to
    forward_to = actions_block.get("forward_to")
    if forward_to:
        try:
            agentmail_client.inboxes.messages.forward(
                inbox.inbox_id, request_row["source_message_id"],
                to=[forward_to],
                text=(
                    f"[Approval inbox - {decision.upper()}]\n\n"
                    f"Type: {request_row['type']}\n"
                    f"Summary: {request_row['summary']}\n"
                    f"Decided by: {decision}\n\n"
                    f"Fields: {json.dumps(fields, indent=2)}\n\n"
                    f"Original email forwarded below."
                ),
            )
            confirmations.append(f"forwarded to {forward_to}")
        except Exception as e:
            print(f"  ! forward failed: {e}")
            confirmations.append(f"forward to {forward_to} FAILED ({e})")

    # 2. webhook
    webhook = actions_block.get("webhook")
    if webhook:
        ok = _post_webhook(webhook, {
            "request_id": request_row["id"],
            "type": request_row["type"],
            "decision": decision,
            "summary": request_row["summary"],
            "fields": fields,
            "source_sender": request_row.get("source_sender", ""),
            "decided_text": (decision_args or {}).get("text", ""),
        })
        confirmations.append(f"webhook {'fired' if ok else 'FAILED'}")

    # 3. reply_to_sender
    reply_template = actions_block.get("reply_to_sender")
    if reply_template:
        sender = request_row.get("source_sender", "")
        if not sender:
            confirmations.append("reply_to_sender skipped (no source sender on record)")
        else:
            try:
                # Interpolate fields into the template
                merged = {**fields,
                          "decision": decision,
                          "reason": (decision_args or {}).get("reason", ""),
                          "changes_text": (decision_args or {}).get("changes_text", "")}
                body = _interpolate(reply_template, merged)
                agentmail_client.inboxes.messages.reply(
                    inbox.inbox_id, request_row["source_message_id"],
                    text=body,
                )
                confirmations.append(f"replied to {sender}")
            except Exception as e:
                print(f"  ! reply_to_sender failed: {e}")
                confirmations.append(f"reply to {sender} FAILED ({e})")

    if not confirmations:
        confirmations.append("(no side-effect actions configured for this decision)")

    return confirmations
