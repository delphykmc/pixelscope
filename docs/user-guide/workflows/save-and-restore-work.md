# Save and Restore Work

Use a **Session** to resume a broader PixelScope working state. Current PixelScope uses the Session workflow for saving; older Comparison Set files remain a compatibility input rather than a separate current save workflow.

## Save a Session

Choose **File > Save Session...**. PixelScope writes a `.pixelscope` JSON Session artifact containing durable workflow intent such as registered/selected source identity, page context, applicable Active/Primary roles, layout, ROI/Line state, display state, and resolved RAW/YUV interpretation needed to reopen the sources.

A Session does not own decoded arrays, caches, workers, or generated Difference maps.

## Inspection viewport and Memo

Session does not persist a durable per-source physical zoom/center snapshot. Use [Memo](review-findings.md) to save ROI notes and captured evidence. Opening a Memo can restore the recorded original view after source verification; it is not a replacement for the wider Session workflow.

## Open a Session

Choose **File > Open Session...** and select the saved `.pixelscope` file. PixelScope validates and stages restore information before replacing the current workspace. Missing source paths can prevent complete reconstruction because saved work references source files rather than embedding them.

Restoring a Session does not make a previously calculated Difference automatically valid for changed inputs. An eligible Difference recipe may be restorable, but explicit current calculation authority remains separate from a persisted map/cache.

## Legacy Comparison Sets

Legacy `pixelscope-comparison-set` v1 files remain readable through **Open Session...**. They preserve the narrower saved selection/order/Active/Primary/layout/RAW contract they originally owned; there is no separate current Open/Save Comparison Set UI.

## Open Recent

The File menu provides typed recent entries for Images, Folders, and Sessions. They are best-effort path history and do not own selection, source residency, Difference, or analysis state.

Unavailable network paths remain listed without being checked during startup or menu
display. Recent Images and Folders check their locations in the background. Sessions
are read and their source paths checked in the background before restoring the
workspace. **Cancel path check** cancels pending Session or file-dialog preparation;
cancelled results cannot replace your workspace or open a chooser later. A network
operation already running in Windows may still take time to return, including while
the application finishes closing.

## Troubleshooting keywords

**Session**, **Comparison Set**, **Open Recent**, **missing source**, **restore**, **RAW profile**, **YUV profile**, **.pixelscope**.
