# Runtime Diagnostics

Use **Help > Copy Diagnostics** when you need a compact runtime snapshot for troubleshooting.

## What it reports

The copied diagnostic text summarizes bounded runtime state such as decoded-source residency, Difference cache usage, foreground/preload workers, preload counters, stale-result counters, and recent accepted failures.

## Privacy and behavior

The diagnostic formatter is designed to sanitize sensitive details such as source paths, credentials, traceback context, and unnecessary failure detail. Copying diagnostics is observational: it does not scan image files, change selection, touch cache/LRU ownership, start/cancel loads, calculate Difference, or change the viewer.

The output is intended to be stable enough for issue/review discussions without becoming another source of application state.

## Troubleshooting keywords

**Copy Diagnostics**, **residency**, **Difference cache**, **preload**, **stale result**, **worker**.
