# PixelScope quality contract

## General merge expectations

Runtime/source/test changes require focused coverage plus the repository-wide owner
validation contract. Documentation-only changes may use the narrower documentation
contract when explicitly scoped as docs-only.

Do not claim a validation PASS that was not observed.

## Core correctness invariants

Tests and reviews must preserve:

- `Registered → Selected → Current Comparison Page → Presented → Resident when
  required` ownership;
- `Analysis Working Set = Current Comparison Page`;
- Selected may exceed six without Selected-wide eager decode/protection;
- source residency uses exact native `source.nbytes` and a protected soft budget;
- Difference cache is independent of source residency;
- Folder Position preload remains exactly `+1`, one position, max-one speculative
  worker unless a separately approved phase changes it;
- Comparison Page navigation creates no speculative preload;
- Display Gain is presentation-only and cannot mutate native analysis identity;
- Difference native/normalized domain semantics remain unchanged;
- RAW Black/White and profile-resolution semantics remain unchanged unless explicitly
  scoped.

## P4-A regression expectations

P4-A temporary curation must remain ID-only and non-persistent. Pick/Unpick/Clear may
not gain decode, residency, preload, Difference, Display Gain, Statistics, Histogram,
or Line Profile ownership. Keep Selection must preserve captured baseline ordering and
use the normal Selected mutation path.

## P4-B Comparison Set schema quality

Comparison Set v1 needs Qt-free domain/repository coverage for:

- supported kind/schema v1 round trip;
- exact Selected source ordering;
- normalized absolute paths;
- duplicate source-path rejection;
- optional Active/Primary member validation;
- layout validation;
- resolved RawProfile round trip through existing validation;
- unresolved RAW representation without fabricated profile state;
- malformed JSON and invalid root/field types;
- wrong artifact kind;
- unsupported/future schema version rejection;
- explicit same-version unknown-field behavior;
- atomic-save output validity.

Artifact parsing/validation must complete before workspace mutation begins.

## P4-B runtime/lifecycle quality

Runtime/UI integration coverage must prove:

- Save Comparison Set serializes current logical Selected, never the temporary Pick
  Set;
- Keep Selection output is the logical Selected payload subsequently saved;
- Save does not clear an active Pick workflow;
- save does not trigger source decoding or Selected-wide residency/protection;
- Open restores exact loadable saved ordering;
- pre-existing Registered non-set documents remain Registered;
- saved Active restoration derives the correct Current Comparison Page rather than
  restoring a serialized page offset;
- applicable Primary and stable layout are restored through existing runtime paths;
- corrupt/incompatible artifact leaves workspace unchanged;
- zero-loadable valid artifact leaves workspace unchanged;
- partial missing artifact loads only valid members in saved order;
- Comparison Set open invalidates captured P4-A curation through the inherited
  Selected mutation path;
- resolved RAW profile is available before foreground source use;
- unresolved RAW remains on inherited lazy profile-resolution semantics;
- large Comparison Sets remain bounded to Current Comparison Page foreground load and
  protection rather than Selected-wide work;
- Split/Difference derived identities are not persisted;
- no new Comparison Page preload or worker pool is introduced;
- Settings schema remains v5.

Resource/lifecycle assertions are preferred over wall-clock timing thresholds.

## Missing/corrupt behavior

Missing source files are a supported workflow condition, not an automatic whole-set
failure. Tests must distinguish partial-load behavior from zero-loadable behavior.

Malformed JSON, wrong kind, invalid required schema, and future schema must be
non-destructive. Tests should snapshot relevant workspace state before an invalid open
and confirm it remains unchanged.

## Privacy quality

Comparison Set v1 contains local absolute paths. Documentation must make that explicit.
Diagnostics must not implicitly expand to include Comparison Set contents or path
history. P4-B adds no telemetry or remote sync.

## Focused P4-B validation

Owner-local focused command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_comparison_set.py tests\ui\test_p4b_comparison_set.py
```

Because P4-B changes runtime/source/tests, the full validation contract is:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

The Chat implementation agent does not bootstrap the owner's Windows `.venv` or
install dependencies to manufacture local validation evidence.

## Review gate

P4-B is not Complete until:

1. implementation and focused tests are present;
2. durable documentation matches actual branch behavior;
3. owner-local validation evidence is reported;
4. independent review blockers are resolved;
5. branch/PR is ready and merged.

P4-C runtime implementation must not begin before that P4-B merge gate is crossed.
