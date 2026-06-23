from pathlib import Path

import yaml

from openlakehouse.policy.models import PolicyDocument, Role


def load_policy(path: str | Path) -> PolicyDocument:
    raw = yaml.safe_load(Path(path).read_text())
    doc = PolicyDocument.model_validate(raw)
    # Role name in YAML is the dict key, not repeated inside the role body —
    # backfill it so Role.name is always populated regardless of input shape.
    for role_name, role in doc.roles.items():
        if not role.name:
            doc.roles[role_name] = Role(
                name=role_name, rules=role.rules, can_execute_queries=role.can_execute_queries
            )
    return doc
