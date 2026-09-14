# Use Remote IQA

Remote IQA is an optional configured workflow for submitting eligible standard-image comparisons to an external Image Quality Assessment service and inspecting published results. Local Files/Image View/Statistics workflows do not require this service.

## Configure Remote IQA

Open **Edit > Settings... > Remote IQA** and configure the deployment values supplied by your environment owner:

- **Server base URL** — the HTTP(S) service endpoint.
- **Root ID / Client path** mappings — portable storage identifiers mapped to paths available on this machine.
- **Staging root** — optional configured logical root used when a submitted source must be staged.

PixelScope submits portable logical storage identity rather than assuming the server sees the same Windows path. Changing a mapping can invalidate an in-progress native Scene verification that was created under the old mapping.

## Submit Current Pair

Use the IQA **Setup** tab when the Current Comparison Page contains exactly two eligible sources. Current remote evaluation accepts standard PNG/JPG/JPEG/BMP **RGB8** sources with three channels and matching original dimensions. PixelScope does not silently convert Gray, RGBA, RAW, RGB16, YUV, or mismatched dimensions to make the pair eligible.

Primary, Active, view order, Single/Multi View, Display Gain, Difference, and Split presentation do not redefine the underlying two submitted documents.

## Submit Folder Pair

Folder Pair prepares deterministic bulk evaluation from Folder A and Folder B:

1. Choose the two folders.
2. Use **Validate / Preview**.
3. Confirm the Scene count/order.
4. Use **Submit Folder Pair**.

The current preparation contract uses immediate eligible PNG/JPG/JPEG/BMP files, excludes symlink inputs, sorts each folder deterministically, requires the same non-zero eligible count, pairs by sorted index, limits a request to 512 pairs/Scenes, and requires matching dimensions per pair. The client preview is intentionally bounded rather than eagerly decoding an entire large folder.

Folder Pair preparation does not register/select every batch source in the local Files workspace.

## Track Jobs

Use the **Jobs** tab while the remote job runs. Jobs can report lifecycle states such as queued, preparing, extracting, aggregating, writing, succeeded, partial, failed, or cancelled.

**Cancel** requests cancellation for a non-terminal job; the service owns the final state. A terminal successful/partial job does not automatically replace the current Results view. **Open Result** becomes available only after PixelScope has a published compatible result reference that resolves through the current storage mapping.

## Open an existing result

Use **File > Open IQA Result...** or **Open Result** from a tracked job. Results open summary-first so the workspace can show dataset/Scene-level measurements without loading every spatial grid immediately.

The IQA **Reference** is local to the IQA result workspace and is independent from the image viewer's **Primary** role.

## Inspect a Scene in Viewer

**Inspect in Viewer** is the explicit transition from passive result browsing to native PixelScope image inspection. Availability requires a compatible result/Scene, a supported number of variant bindings, configured storage roots, eligible standard-image sources, and successful source verification. PixelScope verifies all required bindings before changing the local workspace; a failed verification does not partially select a Scene.

After successful Inspect, verified unique sources enter the normal Registered/Selected/current-page workflow and the normal ROI, Statistics, Histogram, Line Profile, Difference, zoom/pan, and source-residency semantics apply.

Use **Return** to restore the pre-Inspect comparison when that temporary return target is still valid. Newer local selection/layout/Primary/curation intent can invalidate Return rather than being overwritten by an older snapshot.

## Partial results

A partial result exposes successfully published Scenes plus diagnostics for requested Scenes that failed or were cancelled. Successful Scenes remain available for normal result exploration and eligible native Inspect. A zero-success job is not presented as a successful partial result.

## Deployment limitation

The repository contains the client/UI integration, but availability and real-service qualification depend on the deployment's GPU service and shared-storage environment. Do not interpret this guide as evidence that an external service is configured for every PixelScope installation.

## Troubleshooting keywords

**Remote IQA**, **RGB8**, **Submit Current Pair**, **Submit Folder Pair**, **Validate Preview**, **Jobs**, **Open Result**, **Inspect in Viewer**, **Return**, **Root ID**, **staging root**, **partial result**.
