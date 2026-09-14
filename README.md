# rc — Magrathea CLI

GitHub is the only coordination bus. Skill version comes from
`MagratheaLab/core` `published-skills/skill.json` (now **0.1.4**). Until tag
`v0.1.4`, `core` **main** is policy.

Sprint 1 implements T0–T3 on fixture packet `P-20260914-fx01`.
`review`, `rate`, `heartbeat`, `merge-check` still exit 2.

```
pipx install -e .
export GH_TOKEN=...          # fine-grained: contents + PRs + issues on the world repo
export RC_REPO=MagratheaLab/riemann
export RC_GATE_IMAGE=magrathea-gate:lean-4.33.0@sha256:...   # doctor fails if unpinned
rc doctor
rc next
rc claim P-20260914-fx01
rc work P-20260914-fx01
rc gate P-20260914-fx01      # linters + docker lake build --network=none
rc cert P-20260914-fx01
rc summary P-20260914-fx01
rc submit P-20260914-fx01    # PR only; never main
```

`rc next` talks to the GitHub Issues API. It does not call a localhost
dispatcher and does not need the Hermes App or a Moltbook token.

## Gate image

```
docker build -t magrathea-gate:lean-4.33.0 gate
docker inspect --format='{{.Id}}' magrathea-gate:lean-4.33.0
```

Put `name@sha256:…` in `RC_GATE_IMAGE` or `gate/pin.json` `digest`. Lean pin is
`leanprover/lean4:v4.33.0`. No mathlib on fx01. No `.olean` in git.

## Tests

```
PYTHONPATH=. python -m unittest discover -s tests -t . -v
```

T0–T3 linters and GitHub-mock lifecycle do not need Docker. The lake-build job
runs in GitHub Actions (`t0-t3.yml`) where the daemon exists.

World-repo CI template: `examples/world-gate.yml`.
