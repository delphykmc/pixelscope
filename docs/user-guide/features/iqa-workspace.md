# IQA Reference Workspace

<!-- pixelscope:screenshot iqa-neutral -->

The standard PixelScope **Core** package does not include an IQA implementation. Local
Files, Image View, Statistics, Histogram, Line Profile, Difference, RAW, and YUV
workflows remain available without IQA.

The separate **PixelScope Reference** package demonstrates the public extension
integration with synthetic/mock IQA data. It is intended for architecture evaluation,
UI integration checks, and downstream conformance work; it is not a real remote model
or Enterprise service.

## Open the reference workspace

Launch the Reference package or source entry point:

```powershell
.\.venv\Scripts\pixelscope-reference.exe
# or
.\.venv\Scripts\python.exe -m pixelscope_iqa_reference
```

Use **View > Show IQA Reference** to show or hide the contributed dock. The File action
**Open IQA Reference Result...** opens a deterministic mock published result.

## Mock job flow

The Reference workspace can exercise a representative public-contract flow:

1. submit the current native two-image comparison pair, or use the synthetic fallback;
2. advance the mock job from queued to running to completed;
3. open the published mock result;
4. switch IQA Reference and Scene selections;
5. inspect the normalized result/spatial availability.

No server URL, shared-storage mapping, credential, proprietary model, or confidential
configuration is required.

## Enterprise deployments

A real Enterprise IQA extension is downstream-owned and may use different detailed UI,
settings, model/server, storage, and authentication behavior. The Reference workspace
is an executable example of the public host/contracts, not a specification of the final
Enterprise UI.
