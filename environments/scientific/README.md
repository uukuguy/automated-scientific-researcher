# Isolated scientific environment

Python 3.12 scientific tooling, separate from ASR control/runtime dependencies.
Exact direct pins and the transitive `uv.lock` are checked in. Pandapower 3.5.6
requires NumPy below 2.5 and pandas 2.3; this environment intentionally follows
those requirements rather than selecting incompatible latest releases.

From the repository root:

```sh
uv sync --locked --project environments/scientific
uv run --locked --project environments/scientific pytest environments/scientific/tests -q
```

Optional notebook profile (installed and tested during calibration):

```sh
uv sync --locked --project environments/scientific --group notebooks
uv run --locked --project environments/scientific --group notebooks pytest environments/scientific/tests -q
uv run --locked --project environments/scientific --group notebooks jupyter lab --no-browser --ip 127.0.0.1
```

JupyterLab and ipykernel provide the notebook interface without installing the
entire `jupyter` metapackage. No global kernelspec is installed. The kernel test
launches and shuts down one local kernel using this environment's interpreter.
Only run the notebook server explicitly, in a trusted development workspace.

Reproduce the real electrical calibration into a new output directory:

```sh
uv run --locked --project environments/scientific --group notebooks \
  python environments/scientific/calibrate.py --output /tmp/asr-pandapower-calibration-new
```

The command refuses to overwrite an output directory. It verifies the tracked
fixture subset against its original published artifact hashes, imports the
original MATPOWER input rather than pandapower's bundled case118, performs the
power flow, and exports raw PPC, reordered raw PPC, normalized computed state,
independent validation, converter mappings, hashes and source snapshots.
`pytest` additionally enforces the documented cross-solver difference bounds.

`results/2026-11-02-case118/` is the corrected calibration.
`results/2026-11-02-integer-angle-diagnostic/` preserves the initial initialization
mismatch and its exact source. See
[the calibration report](../../docs/validation/PANDAPOWER-CALIBRATION.md).

This host environment is trusted developer tooling. It is not mounted into
candidate containers, grants no Docker socket, changes no execution capability,
and does not admit trials or replace the MATPOWER reference. The converter's
raw limits/ratings differ from the original problem; normalized state is checked
against the original constraints. Pandapower and MATPOWER share the PYPOWER/
MATPOWER Newton-Raphson lineage, so solver agreement alone is not independent
scientific verification. The existing Python electrical checker is separate.
