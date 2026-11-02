# Pandapower scientific environment calibration

Verified locally on 2026-11-02, macOS arm64, Python 3.12.12. This is a development
calibration of one frozen IEEE-118 operating point, not generalization, formal
replication, a new method, a feasibility claim or a performance comparison.

The isolated environment is [environments/scientific](../../environments/scientific/README.md).
This slice adds no root dependencies and does not change the admitted execution profile.

## Environment and reproducible commands

| Direct package | Pin |
|---|---|
| pandapower | 3.5.6 |
| numpy | 2.4.6 |
| scipy | 1.18.1 |
| pandas | 2.3.3 |
| pyarrow | 26.0.0 |
| networkx | 3.7 |
| matplotlib | 3.11.2 |
| pytest | 9.2.0 |
| jupyterlab, optional `notebooks` group | 4.6.5 |
| ipykernel, optional `notebooks` group | 7.4.0 |

`uv.lock` pins the transitive environment. JupyterLab plus ipykernel supplies the
approved notebook tooling without the full Jupyter metapackage. The complete
profile was installed with `uv sync --locked --project environments/scientific
--group notebooks`. The installed environment contains 122 packages and occupies
about 586 MiB locally. No notebook server was launched or global kernel installed.

```sh
uv run --locked --project environments/scientific --group notebooks \
  pytest environments/scientific/tests -q
uv run --locked --project environments/scientific --group notebooks \
  python environments/scientific/calibrate.py --output /tmp/asr-pandapower-calibration-new
```

Five tests passed: real IEEE-118 comparison, deliberately corrupted voltage,
fixture corruption rejection, sparse numerics/graph/Parquet/PNG roundtrip, and a
real local notebook-kernel execution using the isolated interpreter. The kernel
was shut down after the test. These checks made no model calls.

## Frozen source and matched solve policies

The fixture is an exact subset of the existing published MATPOWER attempt
`trial_attempt_baseline/attempt_baseline`, originally under
`data/p2-supervisor-reference-20261102/evidence/`. Input, solved output and solver
metadata hashes are checked against the copied original manifest. The original
trial/attempt identities and manifest hash remain in
[fixture provenance](../../environments/scientific/fixtures/matpower-case118/provenance.json).
The fixture is not represented as a new MATPOWER run or a complete copy of all
original provenance artifacts. Case-data attribution and MATPOWER's explicit
case-file license exception are retained in `SOURCE-NOTICE.txt`.

Both solvers use the original 118 buses, 54 generators, 186 branches, 100 MVA
base, connected topology, one slack at bus 69 and a 30 degree reference angle.
NR uses constant-power loads, fixed PV/PQ types, no Q-limit switching, no
distributed slack, no voltage-dependent loads and at most 20 iterations.
MATPOWER uses tolerance `1e-10` pu; pandapower uses `1e-8` MVA on the same
100 MVA base. Generator voltage setpoints initialize controlled buses; PQ
magnitudes start at 1 pu, and all initial angles are 30 degrees. Pandapower is
explicitly given `init_vm_pu=1.0`, `init_va_degree=30.0` with `init='auto'`;
this supplies a numeric flat vector and does not request DC initialization.
Iteration traces verify the actual initial angle vector. `trafo_model='pi'`
matches the original branch model. Numba and lightsim2grid are disabled so the
backend cannot silently change. Frequency is explicitly 60 Hz during conversion.

These settings follow the official [AC power-flow options](https://pandapower.readthedocs.io/en/stable/powerflow/ac.html),
[PYPOWER converter](https://pandapower.readthedocs.io/en/stable/converter/pypower.html)
and [unit/sign conventions](https://pandapower.readthedocs.io/en/stable/about/units.html).

## Corrected numerical result

Both solvers converged in four iterations. Maximum absolute differences:

| Quantity | Difference |
|---|---:|
| Bus voltage magnitude | 7.771561172376096e-16 pu |
| Bus angle, absolute reference retained | 1.545430450278218e-13 degrees |
| Generator active output | 1.1368683772161603e-13 MW |
| Generator reactive output | 9.094947017729282e-12 MVAr |
| Branch active flow, both ends | 2.5721647034515627e-12 MW |
| Branch reactive flow, both ends | 9.030998171510873e-12 MVAr |
| Original-model versus converted-model Ybus element | 5.695433295429594e-14 pu |

The independent `powerflow_lab.validation` checker recalculates original-model
currents, injections, controls and operating limits. Maximum power mismatch is
`3.921975549628335e-13` pu for pandapower and `3.935784299266862e-13` pu for the
saved MATPOWER result. Normalized computed state passes input-preservation and
equation checks at the existing `1e-7` pu calibration threshold.

Both results violate the same six reactive-generation limits (original generator
rows 8, 14, 15, 42, 45, 47; zero based). All 186 thermal limits remain unassessed
because the original ratings are absent. Solver convergence is not full operating
feasibility.

Detailed measurements, source/environment hashes and mappings are in
[calibration.json](../../environments/scientific/results/2026-11-02-case118/calibration.json).

## Raw conversion differences: not a lossless problem export

Pandapower represents this case as 175 lines, 9 transformers, 2 impedances,
53 generators, one external grid, 99 loads and 14 shunts. It renumbers buses,
reorders branch rows by element class and moves the slack generator first.
Mappings are recorded explicitly; both transformer endpoint directions are
handled before comparing flows.

After restoring only original bus labels and row ordering, the raw PPC still has
these fixed-column differences from the frozen MATPOWER input:

| Raw fixed field | Rows changed | Maximum absolute difference |
|---|---:|---:|
| Bus VMAX | 118 | 0.94 pu |
| Bus VMIN | 118 | 0.94 pu |
| Slack QMAX / QMIN | 1 each | 300 MVAr each |
| Slack MBASE | 1 | 99 MVA |
| Slack PMAX | 1 | 999999194.8 MW |
| Slack PMIN | 1 | 1000000000 MW |
| Branch RATE_A | 186 | 59755155.30359766 MVA |
| Branch TAP | 175 | 1 |

Raw voltage bounds become 2/0; slack Q bounds become 0/0, MBASE becomes 1,
and P bounds become ±1e9. Missing ratings become synthetic large values.
Untapped line ratios change from MATPOWER's zero sentinel to one. The admittance
audit confirms the electrical model matches at roundoff, but those operational
metadata are not equivalent. The raw aligned case **fails input preservation**
with `fixed input changed`; the checker therefore correctly refuses to call that
raw case equation-valid, even though its calculated mismatch is tiny.

Both [raw PPC](../../environments/scientific/results/2026-11-02-case118/raw-ppc.json)
and [raw aligned case](../../environments/scientific/results/2026-11-02-case118/raw-aligned-case.json)
are retained. The normalized solution explicitly copies frozen fixed metadata
and inserts only computed VM/VA, PG/QG and branch flows. It is an adapter result,
not proof that pandapower preserves those metadata. Original constraints always
govern independent validation; synthetic ratings are never treated as assessed
original limits. Full row indices and column differences are in the audit.

## Preserved initialization diagnostic and limits

The first run passed integer `30` from JSON as `init_va_degree`. In the pinned
pandapower version, `build_bus.get_voltage_init_vector` accepts floats, arrays
and lists but does not accept a plain integer in that scalar branch. The trace
showed non-slack angles starting at zero while the slack stayed at 30 degrees.
That run still converged in four iterations but was not the intended same-start
comparison: maximum VM difference was `2.599365167554879e-12` pu, angle difference
`2.964490875001502e-10` degrees, generator P difference
`1.313560460403096e-8` MW, and mismatch `1.147159173209289e-10` pu.

Its [report and source snapshot](../../environments/scientific/results/2026-11-02-integer-angle-diagnostic/)
remain preserved. Casting the angle to float fixes the initialization; regression
assertions check the actual trace, not merely configured options. No reference
solution or original input was adjusted to improve the comparison.

This verifies one calibration point and one conversion path. It does not cover
other networks, contingencies, multiple-slack policies, Q-limit switching,
arbitrary candidate code, OPF or performance. Pandapower's solver shares the
MATPOWER/PYPOWER lineage; this is cross-implementation calibration, with separate
Python equation checking, not a claim of independent solver ancestry. The
scientific host environment is not candidate isolation and grants no Docker
socket. Its use as an admitted experiment backend requires a separate capability,
policy mapping, resource accounting and supervised execution integration.

## SDK prototype verification

The parent's Context7 lookup used `/e2niee/pandapower`, whose indexed version was
3.5.4. It establishes prototype guidance; it does not establish the installed
3.5.6 signature or behavior. Direct `inspect.signature` against the locked local
installation verified:

```text
from_ppc(ppc, f_hz=50, validate_conversion=False, **kwargs)
runpp(net, algorithm='nr', calculate_voltage_angles=True, init='auto',
      max_iteration='auto', tolerance_mva=1e-08, trafo_model='t',
      trafo_loading='current', enforce_p_lims=False, enforce_q_lims=False,
      check_connectivity=True, voltage_depend_loads=True,
      consider_line_temperature=False, run_control=False,
      distributed_slack=False, tdpf=False, tdpf_delay_s=None, **kwargs)
```

The converter prototype matches the documentation. Installed 3.5.6 explicitly
supports `enforce_p_lims`; no support for additional algorithms is inferred merely
from newer/develop documentation. The angle initialization keywords are consumed
through `**kwargs`; their local implementation and the actual trace were checked.
[API verification](../../environments/scientific/api-verification.json) records
exact signatures, version and installed-source hashes.

`_from_ppc_lookups`, `_pd2ppc_lookups`, `_ppc` and its iteration/Ybus arrays are
private interfaces used by this version-pinned calibration adapter. They are not
presented as stable public SDK APIs. Upgrading pandapower requires rechecking
those mappings and rerunning this calibration, not only refreshing dependencies.
