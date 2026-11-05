# Named Findings (.pxreview) — W09b integration preview

Named Findings is installed by the application composition root. Open it through
**View > Named Findings** or the **Review** workspace. This integration preview
is not a release announcement. Unlike Session v1, Review stores named historical
evidence.

## Capture a Finding

1. Open and compare the intended sources, choose Reference/Target and
   inspection ROI/Line, channel, Display Gain and physical zoom.
2. Open **View > Named Findings**. Provide a Title, optional Note and comma-separated
   Tags, then select **Add Finding**.
3. The application records the W04 view state and the W02 analysis snapshot
   **only if its presented/current tokens match**. Pending, stale,
   cancelled or uncomputed results are explicitly unavailable.
4. Candidate file bytes, native interpretation and loaded samples are
   independently checked in a bounded worker before committing a Finding.
   Recording does not calculate Difference or silently reload an image.
5. Edit metadata or delete a Finding from the list. Metadata edits do not
   change the captured numeric evidence or its timestamp.

## Save, reopen and inspect

Use **Save .pxreview** to write a validated Review atomically. A changed
existing Review requires a loaded matching revision and overwrite approval.
**Open .pxreview** validates the file before replacing the displayed historical
library; it does **not** change the current image workspace.

Historical snapshots remain labelled as **past captured evidence**. Opening
them does not establish that current source files or current measurements
are identical.

## Verified source binding and restore

Select each exact source candidate, then approve an explicit RAW/YUV profile.
Any relocated path requires separate user confirmation **even if its digest
matches**. Select **Verify Selected Finding**, which checks source SHA-256 and
native interpretation. An unresolved, changed, missing or unsupported source
cannot activate a Finding; offline evidence remains visible.

Only once all required sources are Verified should **Activate verified Finding**
begin canonical Source/Pair/ROI/View State restoration. Pending foreground
loads or display geometry must be handled on authoritative terminal events.
A post-commit failure may leave partial state and must be reported as such.

## Integration restrictions

RAW/YUV candidates with explicit supported profiles and a bounded native decode
budget are the implemented trust slice; general PNG/JPEG capture is unsupported.
Restoration includes ROI/Line, the Difference pair/recipe, display gain, physical
zoom and Sync state. The Sync button reflects the restored state. Restoring a
recipe does not calculate Difference or turn past measurements into current ones;
use Calculate explicitly for a new measurement. Mixed YUV/non-YUV analysis remains
disabled by the existing semantic compatibility rules. User navigation interrupts
a pending restore. Hardware DPI/multiple-monitor and SMB/locked-file acceptance
remain separate environment checks.
