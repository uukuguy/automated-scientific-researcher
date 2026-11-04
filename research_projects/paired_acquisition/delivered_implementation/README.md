# Team-authored generator and adversarial review

These are exact, unmodified deliveries from P5 implementation run
`research_2ab7884ffbcb46b7bbff0a8e7108e077`, project `organization-dd58b2d04033`.
They are research artifacts, not the trusted Control admission validator.

- `paired_generator.py`: worker_1 source frozen in snapshot
  `238ad9b487a182c25f2fa2e8900497e04c6b80a9adb6d4e84b89dfb3ff05f26d`,
  SHA256 `ad498577d9d919bb6cc17c71a5ab970adf5370f8555ed6216a55683a682086ca`.
- `review_generator.py`: worker_2 adversarial harness in snapshot
  `dd752cda09fafa51f2e02f43eb89b256b21f862614c3c0cd438c779b25b71853`,
  SHA256 `05aadf2fdf6d1a6490258a1842e757b26a3fe164ff435767c64c395343f2eb93`.
- `LEAD-FINAL-DISPOSITION.md`: exact Lead report in snapshot
  `f8f3e419c5bdd884b32dce8bb54ea5bb692b5e756e8753b362e0b3b63ee98313`.
- `WORKER-REVIEW-REPORT.md`: exact reviewer report in snapshot
  `f86243592044b9e17d0cb6708c71f42712b3af5496e13afa7d132f08ea087b01`.

Both Python sources actually ran through task-scoped isolated `analysis` jobs.
The generator produces768 unique named coordinates across eight seeds and2048
proposed arm slots. It did not label them or fit a model. Its descriptive manifest
is not an admitted Control paired_sampling protocol.

**Known defect preserved:** the internal oracle derives expected order from the
same ARMS mapping as construction. Reversing TT still reports accepted. The
reviewer demonstrated this failure and separately checked the correct baseline
against literal expected order. Do not use built-in accepted as a generic
protocol verdict. Any repair must preserve this source and add a versioned
implementation with independent checks and actual negative-control regression.

Role source review and analysis are not independent electrical/utility evaluation.
The Lead report describes organizational closure as pending at its publication;
subsequent authoritative Organizer record seq27 closes the direction. Read the
final host receipt for lifecycle state, not a historical report's lifecycle claims.

See [actual run and limits](../../../docs/validation/P5-IMPLEMENTATION-PILOT.md)
and [receipt](../../../docs/validation/P5-IMPLEMENTATION-RECEIPT.json).

Final Organizer report is copied unchanged as `ORGANIZATION-REPORT.md`, SHA256
`3672d4d76bb1e1aa8bd36429beebc9a55f19b0cb01300b2d6665e78e24c0b64c`, snapshot
`1a82d0de58a2e4c2f3bbf3e187ad21e3c57d8e2b87436363ae3d75e814f65705`. All deliveries are acknowledged in the final host receipt.
