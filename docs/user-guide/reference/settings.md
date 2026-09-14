# Settings Reference

Open **Edit > Settings...** to change persistent preferences.

## General

Core General settings include startup/viewer restoration, default workspace mode, Single View pane defaults, default presented file/sync behavior, and default Difference presentation/analysis options.

## Files & Recent

Controls the Recent-entry limit and related file-history behavior. Recent entries are convenience pointers to user resources, not copies of source images.

## Performance

- **Decoded Source Memory**: source residency/cache budget.
- **Difference Map Cache**: Difference result cache budget.
- **Preload**: enables/disables next-position speculative preload.
- **Image/analysis worker limits**: bounds relevant worker concurrency.

Performance settings are independent budgets/controls. Larger values can increase memory use; smaller values can increase reload/recompute frequency.

## Remote IQA

The production composition can add Remote IQA settings used by the service integration. Their correct values are deployment-specific; obtain endpoint/storage details from the environment owner rather than guessing them.

## Reset and restart

Use the dialog's status and reset behavior as the authority for whether a change applies immediately or requires restart. Resetting settings is distinct from deleting image files or saved Sessions.
