# Client addendum 1 — factual delivery corrections

No experiment has been run; hypotheses and scientific choices remain the researcher's.
Original client artifacts and the completed intake snapshot are unchanged.

- Read client-data/index.json and its JSONL pages for complete, lossless public data.
  Pages are at most 40,000 bytes. Row counts and source hashes bind them to the
  original arrays. No private samples or labels are included.
- Exact ID predicate: new_ID_RMSE <= max(1.1 * baseline_ID_RMSE,
  baseline_ID_RMSE + 0.00001 pu). Target predicate: new_target_RMSE <=
  0.8 * baseline_target_RMSE. Both baselines must be evaluated on the corresponding
  same frozen evaluation set. These clarify the original criterion, not outcomes.
- Each x has three regional multipliers. For original bus row i (zero-based),
  group=min(2,floor(3*i/118)). Multiply Pd and Qd by x[group]. For each online
  non-reference generator multiply Pg by total_new_Pd/total_original_Pd.
  Preserve topology, original PV/PQ roles, reference angle, voltage setpoints and
  all other fixed data. The reference generator balances the remaining active
  injection. This is a synthetic dispatch convention, not a feasibility guarantee.
- Labels y are 118 bus voltage magnitudes (pu) followed by 118 bus angles (degrees),
  in original bus-row order. The reference angle is the original 30 degrees.
  Primary mask: original bus type 1. Angle mask: original bus type !=3.
- Train/ID inputs use independent uniform coordinates on [0.9,1.1]^3. Diagnostic
  regime coordinates are independent uniforms on [1.2,1.45], [0.85,1.0],
  [1.05,1.25]. Private evaluation uses fresh independent draws from the stated
  regimes. Private seeds and samples are not provided. These laws describe this
  synthetic client; they are not a learned distribution of real grid operations.
- Reference labels use the pinned pandapower calibration wrapper with fixed
  PV/PQ roles, no Q-limit switching, flat initialization and a 20-iteration cap.
  Independent original-problem validation uses tolerance 1e-7 pu. Solver failure
  remains unresolved, and all operating violations/missing ratings are retained.
- The supplied trainer uses numpy 2.4.6. Its source and all pages are pinned in
  client-addendum-manifest.json. No training or numerical capability is added by
  this addendum. Current numerical allowance remains zero.
