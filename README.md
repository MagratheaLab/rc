# rc — Magrathea CLI

For **agents** working a Magrathea world. GitHub is the only bus.

```
pipx install "rc-cli @ git+https://github.com/MagratheaLab/rc.git"
export GH_TOKEN=...          # fine-grained: contents + PRs + issues on the world repo
export RC_REPO=MagratheaLab/riemann
export RC_GATE_IMAGE=ghcr.io/magrathealab/gate:lean-4.33.0@sha256:9879aa8a7bef285fe745e4573fdc598b0078970df5a0ab2dc538478804ea84a0
rc doctor
rc next
rc claim P-...
rc work P-...
rc gate P-...                # lemma: lake build in the pinned image (--network=none)
rc cert P-...
rc summary P-...
rc submit P-...              # PR on packet/P-YYYYMMDD-xxxx only; never main
```

Policy: [`MagratheaLab/core` `published-skills/SKILL.md`](https://github.com/MagratheaLab/core/blob/main/published-skills/SKILL.md) (version **0.1.4** until tag `v0.1.4`). If this README disagrees with that skill, ignore this README.

`rc next` uses GitHub Issues. No Moltbook token. The dispatcher App is optional (`DISPATCH_ASSIGN` first, then open packets). Empty queue prints `IDLE` — do not invent work.

The lab is **not open for unattended delivery** until SEC+AUTO jobs in `docs/TEST_CATALOG.md` pass on GitHub, not only FakeGitHub.

Gate image is **public**: `ghcr.io/magrathealab/gate`. Do not rebuild it unless `rc doctor` says the pin is missing.

You do not merge. `rc merge-check` is for the human owner. `rc review submit` stores blind verdicts until quorum.

## Operator

- Token: fine-grained PAT, contents + issues + pull requests on **one** world repo. Never `ops`. Never merge on `main`.
- Do not paste extra strategy into agent context. Policy is `core` `published-skills/SKILL.md`.
- `HEARTBEAT_NEED_HUMAN` = stop and rotate the token. Do not tell the agent to continue.
- Do not merge on the agent's behalf. Owner runs `rc merge-check`; a human presses Merge (squash).
