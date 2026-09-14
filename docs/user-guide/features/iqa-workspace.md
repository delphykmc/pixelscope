# IQA Workspace

The IQA workspace is the Image Quality Assessment surface for configured result/submission workflows. Local image comparison does not require a remote IQA service.

## Open the workspace

Use the IQA workspace command or `Ctrl+Shift+I` to show or hide it.

## Main workflow

The workspace provides setup, job/result, and result-inspection surfaces. An **IQA Reference** identifies the reference side of an assessment where the configured workflow requires one. Existing IQA result artifacts can be opened for inspection through **File > Open IQA Result...**.

## Remote service availability

Remote submission depends on deployment-specific service and storage configuration. The repository contains the client/UI integration, but this guide does **not** claim that a real GPU service, shared-storage publication path, or organization-specific infrastructure is available or externally qualified in every installation.

The remote submission input contract is narrower than the local viewer: configured submission currently accepts standard `.png`, `.bmp`, `.jpg`, and `.jpeg` sources rather than treating local RAW/YUV viewing as an implicit remote-conversion pipeline.

## Troubleshooting

If submission is unavailable, verify deployment settings, source eligibility, service reachability, and storage configuration supplied by your environment owner. Local Files/Image View/Statistics workflows remain usable independently.
