# PixelScope documentation

Use durable documentation according to the question being answered:

- [`CURRENT_STATE.md`](CURRENT_STATE.md) — current merged/active implementation
  baseline and product-state snapshot.
- [`PRODUCT_SPEC.md`](PRODUCT_SPEC.md) — user-visible product contract.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — component ownership, data flow, worker,
  registration/selection/presentation, residency, Difference, Display Gain, and RAW
  boundaries.
- [`DECISIONS.md`](DECISIONS.md) — accepted engineering/product decisions.
- [`USER_GUIDE.md`](USER_GUIDE.md) — end-user workflow and controls.
- [`QUALITY.md`](QUALITY.md) — validation and completion contract.
- [`ROADMAP.md`](ROADMAP.md) — phase ordering and planned scope.
- [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md) — active P3
  implementation/validation plan.
- [`exec-plans/completed/`](exec-plans/completed/) — historical completed plans.
- [`PACKAGING_CONSTRAINTS.md`](PACKAGING_CONSTRAINTS.md) — release/package version
  constraints.
- [`BRANDING.md`](BRANDING.md) — application identity and icon rules.
- [`AGENT_HARNESS_NOTES.md`](AGENT_HARNESS_NOTES.md) — repository-specific agent
  workflow lessons.
- [`ui/implementation_status.md`](ui/implementation_status.md) — current UI
  implementation notes.

## Current P3 terminology

P3-D uses the following ownership model throughout durable docs:

```text
Registered -> Selected -> Presented -> Resident when required
```

Registered is Files/catalog membership, Selected is the user comparison set,
Presented is bounded viewer occupancy, and Resident is decoded-native-source memory
ownership. The six-tile viewer capacity must not be interpreted as a registration
limit.

P3-D input intent is:

- **Open Images...** / direct image-file D&D → register + select/present;
- **Open Folders...** / folder D&D → register only;
- mixed D&D → direct files selected while folder contents remain registration-only.

RAW and ordinary images share Open Images while RAW profile/decode policy remains
format-specific internally. Folder RAW registration is lazy so dataset registration
does not force profile dialogs or speculative decoding.
