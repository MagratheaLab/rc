# Magrathea test catalog — for Grok Build

Copied from Drive 2026-09-17. Tester writes; Build implements.
Do not go live until SEC-* and AUTO-* are green on GitHub, not only FakeGitHub.

Live = agents outside the owner laptop deliver a certificate without a human
in the loop after the packet exists.

## Already present (do not redo)

| Id | Where | Note |
|---|---|---|
| T0–T4, T10 | `rc/tests/` | FakeGitHub, one login `tester` |
| S0–S12 | `ops/AGENT_SCENARIOS.md` | Paper + partial text pass |

## This tree (unit)

- SEC-4 secrets inside SUMMARY → `tests/test_sec.py`
- SEC-10 numeric/millennium language → `tests/test_sec.py`
- AUTO-2 empty queue IDLE → `tests/test_auto.py`
- SEC-7 `DISPATCHER_URL=http://127.0.0.1` ignored by `rc next` (same test)

## Still blocked (need owner)

SEC-1/2/5/6 live PAT of user W, App install token, reviews ACL.
AUTO-1/4/5/9 live: fixture packet exists (`riemann` #18 `P-20260924-t8w`). Still needs machine-user W (not owner, not Grok).
Until AUTO-10 is PASS on GitHub: **not live**. No recruiting.
