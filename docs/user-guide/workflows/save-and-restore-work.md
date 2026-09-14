# Save and Restore Work

PixelScope separates reusable source selections from broader workspace/session state.

## Comparison Sets

Use a **Comparison Set** when you want to save and reopen the logical source selection and comparison ordering. Comparison Sets preserve the comparison identity without owning decoded image arrays, caches, or background workers.

## Sessions

Use a **Session** when you want to resume a broader working state. Session data can include registered and selected source identity, current page context, Active/Primary roles, viewer/workspace state, ROI/Line state, display gain, and resolved RAW/YUV interpretation needed to reopen those sources.

Restoring a Session does not make a previously calculated Difference magically valid for changed inputs. Difference remains subject to its explicit current-pair calculation contract.

## Recent entries

Recent items provide typed shortcuts back to recently used images, folders, and sessions. They are convenience history, not a second copy of the source data.

## Portability

Saved work references source paths. Moving or removing source files can therefore produce missing-source behavior on restore. RAW/YUV profile information may be persisted so the interpretation can be reproduced without guessing.

## Troubleshooting keywords

**Comparison Set**, **Session**, **Recent**, **missing source**, **restore**, **RAW profile**, **YUV profile**.
