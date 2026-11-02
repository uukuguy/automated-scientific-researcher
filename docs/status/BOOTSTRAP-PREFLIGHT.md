# Bootstrap Environment Preflight

Checked: 2026-11-02 14:50 (Asia/Shanghai). Scope: WP1 environment discovery only.

| Check | Observed result |
|---|---|
| Parent repository | main at 8b4669c; clean before initialization. |
| Python selection | `.python-version` requests 3.12; `uv python find 3.12 --no-python-downloads` resolves `/opt/homebrew/opt/python@3.12/bin/python3.12`. |
| Selected Python | 3.12.12. |
| Default Python | 3.14.2; do not assume the default matches project selection. |
| uv | 0.10.7. |
| Host | macOS 26.3, arm64. |
| MATLAB / Octave | Neither executable found on PATH; other installation locations were not searched. |
| Python numerical tools | numpy, scipy, pandapower and pypower absent in both inspected interpreters. |
| Project environment | No `.venv`; no dependencies declared in pyproject.toml. |
| Canonical IEEE-118 case | Not tracked; no case118-named file found in the local upstream tree. |
| Local AAR copy | `3th-party/automated-w2s-research`, clean at `79a0562fa1a2c246048ed7c009f3684907987b05`. |
| Upstream setup | README describes uv setup, training dependencies, evaluation server and agent modes; no example executed. |

## Evidence boundary

No power flow was run. No case hash, convergence rate, residual or feasibility result exists.
The environment check is an initial WP1 result; it does not satisfy G1.
No dependency install, service launch or paid API experiment was performed.

## Recheck commands

```sh
uv python find 3.12 --no-python-downloads
/opt/homebrew/opt/python@3.12/bin/python3.12 --version
uv --version
command -v octave matlab
git -C 3th-party/automated-w2s-research rev-parse HEAD
git -C 3th-party/automated-w2s-research status --short
```

## Immediate work boundary

Establish the reproducible WP1 solver environment and canonical MATPOWER case provenance.
Use the specification's reference-tool preference; document any Python fallback and model conversion differences.
Then implement the five baseline scripts and the fixed operating configuration from §10.1.
