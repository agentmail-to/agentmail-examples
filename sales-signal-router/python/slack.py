"""
Slack incoming-webhook fan-out.

Webhook URLs are per-channel: the URL itself determines which channel the
message lands in. The agent supports four optional URLs in .env:

  SLACK_WEBHOOK_URL          — default (required)
  SLACK_WEBHOOK_HOT          — hot replies (falls back to default)
  SLACK_WEBHOOK_ENTERPRISE   — enterprise CRM events (falls back to default)
  SLACK_WEBHOOK_DIGEST       — EOD digest (falls back to default)
"""

import json
import os
import urllib.error
import urllib.request


def _post(url: str, payload: dict) -> bool:
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", errors="replace")
        return body.strip() == "ok"
    except urllib.error.HTTPError as e:
        print(f"  ! slack post failed: {e.code} {e.reason}")
        return False
    except Exception as e:
        print(f"  ! slack post failed: {e}")
        return False


def _url_for(flow: str) -> str:
    """flow: 'hot' | 'enterprise' | 'digest' | 'default'"""
    env_key = {
        "hot": "SLACK_WEBHOOK_HOT",
        "enterprise": "SLACK_WEBHOOK_ENTERPRISE",
        "digest": "SLACK_WEBHOOK_DIGEST",
    }.get(flow, "")
    return (env_key and os.getenv(env_key)) or os.getenv("SLACK_WEBHOOK_URL", "")


# --- alert builders -----------------------------------------------------------


def hot_reply_alert(*, sender: str, summary: str, sentiment: str,
                    deal_owner_slack_id: str, thread_url: str = "") -> bool:
    url = _url_for("hot")
    if not url:
        return False
    mention = f"<@{deal_owner_slack_id}> " if deal_owner_slack_id else ""
    sentiment_emoji = {
        "positive": ":fire:",
        "objection": ":warning:",
        "unsubscribe": ":no_entry:",
        "ooo": ":zzz:",
    }.get(sentiment, ":envelope:")
    text = (
        f"{sentiment_emoji} *Hot reply* ({sentiment}) from `{sender}`\n"
        f"{mention}{summary}"
    )
    if thread_url:
        text += f"\n<{thread_url}|Open thread>"
    return _post(url, {"text": text})


def crm_event_alert(*, sender: str, event_type: str, customer: str,
                    deal_size_usd: float, tier: str, summary: str) -> bool:
    # Enterprise tier uses the dedicated webhook if set
    url = _url_for("enterprise") if tier == "enterprise" else _url_for("default")
    if not url:
        return False
    tier_emoji = {"enterprise": ":rocket:", "mid_market": ":chart_with_upwards_trend:", "smb": ":seedling:"}.get(tier, ":bell:")
    amount_str = f"${deal_size_usd:,.0f}" if deal_size_usd else "(amount n/a)"
    text = (
        f"{tier_emoji} *{event_type.replace('_', ' ').title()}* — {customer or 'unknown customer'} ({tier})\n"
        f"Amount: {amount_str}  ·  Source: `{sender}`\n"
        f"{summary}"
    )
    return _post(url, {"text": text})


def watchlist_alert(*, sender: str, matched_term: str, why: str, summary: str) -> bool:
    url = _url_for("default")
    if not url:
        return False
    text = (
        f":eyes: *Watchlist match* on `{matched_term}` from `{sender}`\n"
        f"_{why}_\n"
        f"{summary}"
    )
    return _post(url, {"text": text})


def digest(*, blocks_text: str) -> bool:
    url = _url_for("digest")
    if not url:
        return False
    return _post(url, {"text": blocks_text})
