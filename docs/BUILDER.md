# Building `rc` (not for world agents)

House SoT is GitLab. MagratheaLab/rc is the published client.

```
PYTHONPATH=. python -m unittest discover -s tests -t . -v
```

`RC_LAKE_MODE=ci` — local linters only; world GitHub Action is `lake build`.
Pin Actions to commit SHAs. `gate/pin.json` must not retrigger image publish.
