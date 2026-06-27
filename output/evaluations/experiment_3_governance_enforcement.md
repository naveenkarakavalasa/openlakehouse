# Experiment 3 — Unified Governance Enforcement

## Purpose
Validate the Canonical Governance Model: default-deny semantics, last-match-wins rule evaluation, `CanonicalAuthorizationDecision` with structured reason codes, and the policy-before-adapter invariant (denied requests never reach the adapter).

## Governance Semantics Verified

| Property | Implementation | Status |
|---|---|---|
| Default-deny | No matching rule → `DENIED_NO_MATCHING_RULE` | ✓ |
| Last-match-wins | Rules evaluated in order; last match wins | ✓ |
| BROWSE/QUERY separation | `can_execute_queries=False` → `DENIED_NO_QUERY_PERMISSION` | ✓ |
| Unknown identity | No role assigned → `DENIED_NO_ROLE` | ✓ |
| Policy-before-adapter | Adapter never called when denied | ✓ |

## Authorization Decision Scenarios

| Identity | Role | Adapter/Schema | Expected | Actual | Reason Code | Adapter Blocked | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| analyst-agent | analyst | databricks_prod/nyctaxi | ALLOW | ALLOW | CanonicalReasonCode.ALLOWED | N/A | ✓ PASS |
| analyst-agent | analyst | databricks_prod/tpch | DENY | DENY | CanonicalReasonCode.DENIED_BY_RULE | YES | ✓ PASS |
| analyst-agent | analyst | aws_prod/openlakehouse_test | ALLOW | ALLOW | CanonicalReasonCode.ALLOWED | N/A | ✓ PASS |
| analyst-agent | analyst | aws_prod/raw_data | DENY | DENY | CanonicalReasonCode.DENIED_NO_MATCHING_RULE | YES | ✓ PASS |
| analyst-agent | analyst | databricks_prod/nyctaxi | ALLOW | ALLOW | CanonicalReasonCode.ALLOWED | N/A | ✓ PASS |
| unknown-bot | none | databricks_prod/nyctaxi | DENY | DENY | CanonicalReasonCode.DENIED_NO_ROLE | YES | ✓ PASS |
| me | admin | databricks_prod/tpch | ALLOW | ALLOW | CanonicalReasonCode.ALLOWED | N/A | ✓ PASS |
| me | admin | aws_prod/raw_data | ALLOW | ALLOW | CanonicalReasonCode.ALLOWED | N/A | ✓ PASS |


## Live Adapter Verification

| Identity | Adapter/Schema | Policy Result | Live Call | Adapter Called | Status |
| --- | --- | --- | --- | --- | --- |
| analyst-agent | databricks_prod/nyctaxi | ALLOW | SUCCESS | True | ✓ |
| analyst-agent | databricks_prod/tpch | DENY (CanonicalReasonCode.DENIED_BY_RULE) | BLOCKED — adapter not called | False | ✓ |


## Policy-Before-Adapter Invariant

Denied requests never reach the adapter layer. Verified by unit tests:

- `test_list_schemas_denied_never_calls_adapter` in `tests/unit/test_tools.py` — ✓ verified
- `test_describe_table_denied_never_calls_adapter` in `tests/unit/test_tools.py` — ✓ verified
- `test_run_query_denied_never_calls_adapter` in `tests/unit/test_tools.py` — ✓ verified

## Reason Code Vocabulary

| Code | Trigger |
|---|---|
| `ALLOWED` | Matched rule with `effect: allow` |
| `DENIED_BY_RULE` | Matched rule with `effect: deny` (last-match-wins) |
| `DENIED_NO_MATCHING_RULE` | Default-deny: no rule matched the resource |
| `DENIED_NO_ROLE` | Identity has no assigned role |
| `DENIED_NO_QUERY_PERMISSION` | Role has `can_execute_queries: false` |
