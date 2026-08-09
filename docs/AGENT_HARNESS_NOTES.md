# Agent harness notes

This file records repository-specific lessons for future Chat/Codex work. It is not
a substitute for product, architecture, or execution-plan documentation.

## Work from the merged baseline

Before implementation or review:

1. resolve the actual latest `main` commit;
2. identify the merged PR that established the current product contract;
3. create/review the requested feature branch from that exact baseline;
4. inspect intervening PRs before applying an older plan;
5. do not infer current behavior from stale roadmap prose alone.

When a newer owner instruction explicitly supersedes an older plan, update durable
docs in the same change so future agents do not resurrect the superseded scope.

## Keep product-state terms exact

PixelScope currently distinguishes:

```text
Registered -> Selected -> Presented -> Resident when required
```

Do not collapse these terms:

- Registered is Files/catalog membership.
- Selected is the user comparison/analysis set.
- Presented is bounded viewer occupancy.
- Resident is decoded-native-source memory ownership.

The six-tile viewer capacity is not a registration limit. Future agents must not
reuse layout capacity as a folder/image registration cap.

P3-D input intent is also explicit:

- Open Images/direct image D&D = register + select/present;
- Open Folders/folder D&D = register only;
- mixed D&D = direct files selected, folder contents registration-only.

Folder registration must not silently invoke selection/render lifecycle or reset
active comparison state.

## Prefer one authoritative path

When consolidating UX, first identify whether the repository already has the
correct low-level path. P3-D did not need a second RAW resolver: `ImageInput`,
registration, `_confirm_raw_profile()`, and existing load workers already supplied
the correct direct-input path. The change instead separated registration ownership
from selection/presentation ownership and added a lazy foreground RAW boundary for
folder registration.

Avoid parallel compatibility helpers when a product decision intentionally removes
an old entry point. Update focused regression tests rather than preserving stale
private APIs only to keep old tests green.

## Preserve worker authority rules

Qt/Python cancellation is advisory. Correctness comes from request identity,
generation/tokens, current-plan authority, and stale-result rejection. Do not
assume cancelling a worker prevents its result callback.

Foreground and preload pools have different ownership. A physically running
preload may become logical foreground authority only under the exact P2 promotion
contract; do not broaden promotion or pool limits casually.

Registration alone should not create decode/preload work. Unresolved folder RAW
must not trigger speculative profile dialogs.

## Avoid timing as a correctness gate

Wall-clock timings are environment dependent. Deterministic tests should assert:

- output values/dtypes/shapes;
- exact native byte accounting;
- decode count;
- request/promotion/cancellation ownership;
- stale-result rejection;
- bounded worker/cache/residency state.

Use timings only as observational characterization unless the owner explicitly
approves a hardware-specific performance threshold.

## Keep source and presentation domains separate

`ImageDocument.source` is authoritative native data. Display Gain and Difference
preview controls are presentation concerns. Statistics, Histogram, Line Profile,
Split Channel source values, Difference domain selection, source generation, and
residency must not accidentally consume gained preview data.

For RAW gain, Black-derived anchors are presentation metadata policy. White Level
remains metadata and is not a substitute for native effective full scale.

## Tests should mirror ownership

For input-policy work, test independently that:

- registration changes Files/catalog membership;
- selection changes only under explicit selection intent;
- presentation stays bounded by viewer geometry;
- decoded residency changes only when source is required;
- folder-only registration preserves active analysis/view state;
- PageUp/PageDown derives from selected folders rather than all registered folders.

Prefer small deterministic fixtures. A large catalog test can use many tiny files;
it does not need large image payloads when registration count is the subject.

## Documentation and validation provenance

Do not claim a test command passed unless its output was actually observed. If the
implementation agent was instructed not to run the Windows `.venv` suite, say so
in the PR and leave owner validation pending.

For code changes, the repository validation contract remains in `docs/QUALITY.md`.
Packaging/signing commands belong only to their approved release scope.

Every agent-assisted commit and PR commentary should retain requested provenance,
including `Co-authored-by: ChatGPT <noreply@openai.com>` when required by the
owner workflow.
