"""
Loads approval_types.yaml and exposes the type list to the classifier prompt
and the action runner. Re-loads on every call so live edits to the YAML take
effect without restarting the agent.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_FILE = Path("approval_types.yaml")


@dataclass
class TypeConfig:
    type: str
    description: str
    classifier_hints: dict  # {senders: [], keywords: []}
    extract_fields: list[str]
    approve: dict  # {forward_to?, webhook?, reply_to_sender?}
    decline: dict


def load() -> list[TypeConfig]:
    if not CONFIG_FILE.exists():
        return []
    try:
        data = yaml.safe_load(CONFIG_FILE.read_text())
    except Exception as e:
        print(f"  ! approval_types.yaml malformed: {e}")
        return []
    out: list[TypeConfig] = []
    for entry in (data or {}).get("types", []) or []:
        out.append(TypeConfig(
            type=entry["type"],
            description=entry.get("description", ""),
            classifier_hints=entry.get("classifier_hints", {}) or {},
            extract_fields=entry.get("extract_fields", []) or [],
            approve=entry.get("approve", {}) or {},
            decline=entry.get("decline", {}) or {},
        ))
    return out


def find(types: list[TypeConfig], type_name: str) -> TypeConfig | None:
    for t in types:
        if t.type == type_name:
            return t
    return None


def render_for_prompt(types: list[TypeConfig]) -> str:
    """Render the configured types as a readable block for Claude's classifier prompt."""
    if not types:
        return "(no request types configured — every email will be discarded)"
    lines = []
    for t in types:
        senders = ", ".join(t.classifier_hints.get("senders", []) or []) or "(no sender hints)"
        keywords = ", ".join(t.classifier_hints.get("keywords", []) or []) or "(no keyword hints)"
        fields = ", ".join(t.extract_fields) or "(no fields)"
        lines.append(
            f"## {t.type}\n"
            f"  - description: {t.description}\n"
            f"  - sender hints: {senders}\n"
            f"  - keyword hints: {keywords}\n"
            f"  - fields to extract: [{fields}]"
        )
    return "\n\n".join(lines)
