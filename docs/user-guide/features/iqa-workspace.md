# IQA Workspace

<!-- pixelscope:screenshot iqa-neutral -->

The IQA workspace is the optional Image Quality Assessment surface for configured submission, job tracking, and published-result inspection. Local image comparison does not require a remote IQA service.

## Workspace areas

The IQA workspace provides **Setup**, **Jobs**, and **Results** surfaces. Setup prepares eligible Current Pair or Folder Pair submissions. Jobs tracks remote lifecycle/progress. Results opens published measurements and optional Scene inspection.

The **IQA Reference** belongs to result analysis and is independent from Image View **Primary**.

## Open the workspace

Use the IQA workspace command or `Ctrl+Shift+I` to show or hide it. Existing published results can also be opened through **File > Open IQA Result...**.

## Remote service availability

Remote submission depends on deployment-specific service and storage configuration. The repository contains the client/UI integration, but this guide does **not** claim that a real GPU service, shared-storage publication path, or organization-specific infrastructure is available or externally qualified in every installation.

The remote submission input contract is narrower than the local viewer: configured submission accepts standard `.png`, `.bmp`, `.jpg`, and `.jpeg` RGB8 sources rather than treating local RAW/YUV viewing as an implicit remote-conversion pipeline.

## Full workflow

See [Use Remote IQA](../workflows/use-remote-iqa.md) for configuration, pair/folder submission, Jobs, Open Result, Inspect in Viewer, Return, partial results, and deployment constraints.
