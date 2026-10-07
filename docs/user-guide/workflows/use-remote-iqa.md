# Use the IQA Reference Mode

The public PixelScope distribution has two explicit modes:

- **Core** — the default product, with no IQA implementation;
- **Reference** — Core plus the MAIN-owned synthetic/mock IQA extension.

The historical public P5 Remote-IQA client is no longer part of the default production
path. Real server/storage/auth/model integration belongs to an Enterprise extension.

## Launch Reference mode

From an installed development environment:

```powershell
.\.venv\Scripts\pixelscope-reference.exe
```

or:

```powershell
.\.venv\Scripts\python.exe -m pixelscope_iqa_reference
```

## Exercise the public IQA contract

1. Register/select two native images if you want the current comparison pair represented.
2. Open **View > Show IQA Reference**.
3. Choose **Run Mock IQA**.
4. Advance the mock job through queued, running, and completed.
5. Open the result.
6. Change the IQA Reference and Scene controls to inspect normalized result behavior.

If the current comparison page is not exactly two native source slots, the Reference
extension uses a synthetic pair rather than guessing or truncating the page.

## Existing mock result

**File > Open IQA Reference Result...** publishes and opens the deterministic fixture
without an external backend.

## What is intentionally absent

Reference mode does not ask for server URLs, shared-storage roots, staging paths,
credentials, SSO, proprietary payloads, or model configuration. Those concerns are not
owned by public Base settings.

Historical Remote-IQA behavior remains documented in the repository's durable
`REMOTE_IQA_*` contract/history documents for implementation archaeology; it is not a
current public deployment workflow.
