import pytest

from openlakehouse.policy.loader import load_policy

POLICY_YAML = """
identities:
  claude-desktop-analyst: analyst
default_role: null
roles:
  analyst:
    can_execute_queries: true
    rules:
      - effect: allow
        adapter: db1
        catalog: sales
        schema: "*"
        table: "*"
      - effect: deny
        adapter: db1
        catalog: sales
        schema: pii
        table: "*"
"""

BAD_POLICY_YAML = """
identities: {}
roles:
  analyst:
    rules:
      - effect: maybe
        adapter: db1
"""


def test_load_policy_round_trips(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY_YAML)

    doc = load_policy(path)

    assert doc.identities == {"claude-desktop-analyst": "analyst"}
    assert doc.default_role is None
    role = doc.roles["analyst"]
    assert role.name == "analyst"
    assert role.can_execute_queries is True
    assert len(role.rules) == 2
    assert role.rules[0].effect == "allow"
    assert role.rules[1].schema_name == "pii"


def test_load_policy_rejects_invalid_effect(tmp_path):
    path = tmp_path / "bad_policy.yaml"
    path.write_text(BAD_POLICY_YAML)

    with pytest.raises(Exception):
        load_policy(path)
