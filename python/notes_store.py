"""
Markdown-with-frontmatter notes store.

Each note is a single Markdown file in `notes/<YYYY-MM-DD>-<slug>.md`. The
file is the source of truth — the agent always re-reads from disk so the
user can edit notes by hand and the agent will pick up the changes.

Frontmatter (YAML) at the top of each file:
    ---
    source: "Fwd from Sarah Chen, 2026-04-29"
    date: "2026-04-29"
    thread_id: "<message-thread-id-from-agentmail>"
    tags: [work, q3-planning]
    ---

Body is the structured content (DECISIONS / ACTION ITEMS / OPEN QUESTIONS /
KEY FACTS), rendered for human readability.
"""

import re
from datetime import datetime
from pathlib import Path

NOTES_DIR = Path("notes")


def _slugify(text: str, max_len: int = 40) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:max_len] or "note"


def _yaml_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(str(x) for x in v)}]")
        else:
            # Quote string values that contain special chars
            sv = str(v).replace('"', '\\"')
            if any(c in sv for c in ":,#[]"):
                lines.append(f'{k}: "{sv}"')
            else:
                lines.append(f"{k}: {sv}")
    lines.append("---")
    return "\n".join(lines)


def find_by_thread(thread_id: str) -> Path | None:
    """Return the existing note for this thread, if any (for dedup)."""
    if not NOTES_DIR.exists() or not thread_id:
        return None
    for p in NOTES_DIR.glob("*.md"):
        try:
            head = p.read_text(encoding="utf-8")[:2000]
        except Exception:
            continue
        if f'thread_id: {thread_id}' in head or f'thread_id: "{thread_id}"' in head:
            return p
    return None


def write_note(*, source_summary: str, thread_id: str, tags: list[str],
               summary: str, decisions: list[str], action_items: list[dict],
               open_questions: list[str], key_facts: list[str],
               existing_path: Path | None = None) -> Path:
    """Write a note file. If existing_path is given, overwrites it (dedup).
    Returns the path."""
    NOTES_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    if existing_path and existing_path.exists():
        path = existing_path
    else:
        slug_seed = (tags[0] if tags else "") + " " + summary[:40]
        path = NOTES_DIR / f"{today}-{_slugify(slug_seed)}.md"
        i = 1
        while path.exists():
            path = NOTES_DIR / f"{today}-{_slugify(slug_seed)}-{i}.md"
            i += 1

    meta = {
        "source": source_summary,
        "date": today,
        "thread_id": thread_id or "",
        "tags": tags,
    }

    body_lines = [_yaml_frontmatter(meta), "", f"# Summary", "", summary, ""]

    if decisions:
        body_lines += ["## Decisions", ""] + [f"- {d}" for d in decisions] + [""]

    if action_items:
        body_lines += ["## Action items", ""]
        for ai in action_items:
            owner = ai.get("owner") or "(unassigned)"
            task = ai.get("task") or ""
            deadline = ai.get("deadline") or ""
            urgency = ai.get("urgency") or ""
            tail = " · ".join(x for x in (deadline, urgency) if x)
            tail_str = f"  ({tail})" if tail else ""
            body_lines.append(f"- **{owner}**: {task}{tail_str}")
        body_lines.append("")

    if open_questions:
        body_lines += ["## Open questions", ""] + [f"- {q}" for q in open_questions] + [""]

    if key_facts:
        body_lines += ["## Key facts", ""] + [f"- {f}" for f in key_facts] + [""]

    path.write_text("\n".join(body_lines), encoding="utf-8")
    return path


def parse_frontmatter(text: str) -> dict:
    """Cheap YAML-ish parser for our own frontmatter (we control the format)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    out: dict = {}
    for line in block.strip().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            out[k] = [x.strip().strip('"') for x in v[1:-1].split(",") if x.strip()]
        elif v.startswith('"') and v.endswith('"'):
            out[k] = v[1:-1]
        else:
            out[k] = v
    return out


def list_all() -> list[dict]:
    """Return all notes' metadata + summary line, sorted newest first."""
    if not NOTES_DIR.exists():
        return []
    items = []
    for p in sorted(NOTES_DIR.glob("*.md"), reverse=True):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = parse_frontmatter(text)
        # First non-empty line after the body's "# Summary" header
        summary = ""
        after_fm = text.split("---", 2)[-1] if text.count("---") >= 2 else text
        m = re.search(r"# Summary\n+(.+?)(?:\n\n|\n#)", after_fm, re.DOTALL)
        if m:
            summary = m.group(1).strip().replace("\n", " ")
        items.append({
            "path": str(p),
            "date": meta.get("date", ""),
            "tags": meta.get("tags", []),
            "thread_id": meta.get("thread_id", ""),
            "source": meta.get("source", ""),
            "summary": summary,
        })
    return items


def search(query: str, limit: int = 10) -> list[dict]:
    """Cheap keyword + tag search. For >100 notes, swap for embeddings."""
    items = list_all()
    if not items:
        return []
    q_terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
    scored = []
    for item in items:
        text = (item["summary"] + " " + " ".join(item["tags"]) + " " + item["source"]).lower()
        # Also pull the body for full-text
        try:
            body = Path(item["path"]).read_text(encoding="utf-8").lower()
        except Exception:
            body = ""
        score = 0
        for t in q_terms:
            score += text.count(t) * 3 + body.count(t)
            if t in item["tags"]:
                score += 5
        if score > 0:
            scored.append((score, item))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [item for _, item in scored[:limit]]


def read_note_excerpt(path: str, max_chars: int = 1500) -> str:
    """Read a note's body (after frontmatter) for inclusion in a Claude turn."""
    p = Path(path)
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:].lstrip()
    return text[:max_chars]
