# PR #179 Sandbox acceptance results — 2026-10-15

This is the initial B1/B4/C1 execution record. The owner's later authorization,
additional failure/repair and revision upgrade tests, packaging work and merge
disposition are recorded in the [follow-up report](issue-176-merge-readiness-results.md).
Statements below about uncommitted files and unrun packaging/full tests describe
the initial execution, not the later follow-up.

ChatGPT-assisted local execution against implementation
`dce97be97b70973b7400ecd7b6706e8b74f6ee4f`, checkout `verify-issue176-m3`.
PR branch is `issue-176-m3-consented-core-conversion` with the same HEAD.
The [runner instructions](issue-176-sandbox-runner.md) describe reusable execution.

## Observed results

| Case | Verdict | Actual ExitCode | Core EXE / HKCU64 | Downstream EXE / HKCU64 | Additional evidence |
| --- | --- | --- | --- | --- | --- |
| B1 interactive No | PASS | 1 | Retained, identical captured identity | Absent / absent | Actual Korean No ID 7; consent-refusal log |
| B4 actual Core running | PASS | 1 | Retained, identical captured identity | Absent / absent | Core still running; process-refusal log |
| C1 installed dependency fault | PASS | 77 | Retained, identical captured identity | Present / present | Verifier exit 21; PARTIAL log; warning acknowledged |

Guest Windows build: `10.0.26100`, x64, Windows PowerShell
`5.1.26100.9444`; host reported Windows 11 Education. Each case used a fresh
Sandbox, installed actual Core through its unchanged setup, and shut down after
saving results. Existing owner Sandbox was closed by the owner before execution.
No manual installer actions were needed for the final PASS runs.

Installer SHA-256:

- Core: `135E3775394D077E5A1CC518C2D4D6432244D6E9AE7E97A971D73A8422807303`.
- Downstream: `30441EC0BAB8952C19D83BAA65BB3E38C3333C6918E0233FA188BA25B00D6D56`.

C1 used the actual Finish-page checkpoint after installation success and before
conversion verification. The installed manifest's intact `_bz2.pyd` (83,736 bytes,
SHA-256 `62173A8FADD4BF4DD71AB89EA718754AA31620244372F0C5BBBAE102E641A60E`)
was replaced inside the guest with four bytes. Its resulting hash was
`054EDEC1D0211F624FED0CBCA9D4F9400B0E491C43742AF2C5B0ABEBF0C990D8`.
The production verifier remained intact. Final log:

```text
02:33:57.483 Conversion withheld: full payload manifest verification failed with exit code 21
02:33:57.483 PARTIAL CONVERSION: downstream installed; Core retained or uncertain.
02:33:57.878 User chose OK.
02:33:57.878 Deinitializing Setup.
```

Actual setup process exit was 77, not inferred from those logs. Core EXE remained
SHA-256 `9BF545A2598061E5D8A25977CE31211FFBB0C113E79BCA6A77920F5AA7998273`,
FileVersion/ProductVersion `0.1.0`, with unchanged captured uninstall fields.
Downstream EXE FileVersion/ProductVersion and registry DisplayVersion were
`0.1.0.1`; DisplayName was `PixelScope Test Edition 0.1.0.1` and InstallLocation
was the canonical guest `LocalAppData\Programs\PixelScopeTestEdition` folder.

## Raw evidence and initial harness limitations

Dedicated output parent:
`C:\Users\Public\Documents\ESTsoft\CreatorTemp\PixelScopeSandbox`.

- B4 PASS: run `20261015-021559-157d3d13ef50413fb3c638ad37b6f090`, `B4/`.
- Final B1/C1 PASS: run `20261015-023214-2ac97978612c4599aeef9147988a4d01`,
  `B1/`, `C1/`, `summary.json`, `report.md`.
- Earlier B1/C1 attempts were BLOCKED by localized Yes/No labels, the observed
  `Next` caption and Inno's localized OK ID 2. Their raw results were preserved
  under the earlier run folders, including
  `20261015-021848-43c95b3ef802436094be10b6ea69e321` and
  `20261015-022744-4b6e688bbd244d14b694428b7323c973`.
  These were harness navigation limitations, not observed installer defects.
  The runner now uses observed captions, standard consent IDs, warning IDs 1/2,
  process-scoped UI discovery and asynchronous clicks.

Each result includes before/after EXE hash/version, uninstall identity fields,
actual exit, OS, UI actions and fault evidence. Core/downstream installer logs
and guest transcripts are retained. Outputs alone are writable mappings; no
repository folder or host application data was mapped. Both input installer
hashes were checked independently inside each guest.

## Validation and delivery

- `python -m pytest -q tests/unit/test_sandbox_runner.py tests/unit/test_release_target_descriptor.py`:
  **46 passed in 17.67s**.
- Subsequent `python -m pytest -q tests/unit/test_sandbox_runner.py`:
  final harness **5 passed in 8.65s**.
- PowerShell parser: both scripts PASS.
- `python scripts/check_docs.py`: `Documentation contract passed.`
- `python -m ruff check tests/unit/test_sandbox_runner.py`: exit 0.
- `python -m ruff format --check tests/unit/test_sandbox_runner.py`:
  `1 file already formatted`.
- `git diff --check`: exit 0. Existing tracked files have no contractions;
  new harness/docs/tests are additive. Owner's pre-existing untracked files remain.
- Actual host commands: `sandbox-runner.ps1 -PrepareOnly`, default B1/B4/C1 run,
  retries `-Cases @('B1','C1')`, `-Cases C1 -TimeoutSeconds 180`, and final
  `-Cases @('B1','C1') -TimeoutSeconds 180`.

Changed files: `scripts/sandbox-runner.ps1`, `scripts/sandbox-guest.ps1`,
`tests/unit/test_sandbox_runner.py`, this report, the runner instructions and
the [completed execution plan](exec-plans/completed/issue-176-sandbox-validation.md).
Local changes are uncommitted; no commit/push or human-commit rewrite occurred.
The PR result comment uses the authenticated `delphykmc` GitHub connector account
and is explicitly marked ChatGPT-assisted.
The [posted result summary](https://github.com/delphykmc/pixelscope/pull/179#issuecomment-6174461782)
omits local output paths. Automatic approval review rejected the initial detailed
comment because it included local paths/build details; the verified-destination,
public-safe summary succeeded. Complete raw evidence remains local.

## Remaining gates

No product failure was observed in B1/B4/C1. These results do not qualify Core
uninstaller failure, interrupted/retried conversion, downstream revision upgrade,
full user-state preservation, downstream GUI smoke or PRIVATE SUB production
acceptance. Other Inno/localized wizard shapes may still require the documented
manual guest checkpoint or a disposable debugger-controlled VM.

No HOST Core install/uninstall/update was invoked, no packaging tool was run,
and no release artifact, manifest, revision or integrity gate was changed.
Existing manifest provenance `0cf9c0c` was preserved separately from the later
installer implementation HEAD. Existing B2/B3 and compile/bundle PASS remain
prior evidence. PR #179 is not merged and its Draft status is unchanged.
