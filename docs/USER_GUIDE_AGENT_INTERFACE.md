# User Guide agent interface — WP-Help-D

This work package exposes **existing, checked-in end-user documentation** to
repository-aware agents without turning PixelScope into an LLM client. The
canonical authority remains `docs/user-guide/`. The generated static site and
installed `help/` are version-matched renderings, not competing documentation
corpora. No image or Remote IQA contents are indexed or sent anywhere.

## Delivered local interface

- `docs/user-guide/llms.txt` lists every canonical MkDocs navigation route
  relative to the generated site root, plus common question-to-page examples.
  It is included in the offline Help bundle and optional publication artifact.
  It does **not** introduce a new external `llms-full.txt` promise or an online URL.
- `python scripts/search_user_guide.py "RAW14 stride"` searches only the
  repository's canonical User Guide Markdown. `--json` returns a bounded list
  of `title`, `heading`, repository-relative `source`, one-based source `line`,
  generated HTML `route`, and a short `snippet`. `--limit` is bounded
  to 1–20 and defaults to five. Zero hits produce an empty JSON array.
- Search is lexical/deterministic and dependency-free: no network, embeddings,
  authentication, inferred authority, mutable index/cache, model invocation,
  screenshot-byte indexing, or generated `site/` dependency. Results are
  **retrieval candidates, not verified answers**. The consumer must read the
  cited Markdown in its own checked-out revision before stating a behavior
  as a fact. Source line references can change in later revisions.
- This CLI is repository-side tooling, **not bundled into PixelScope.exe**.
  Installed users already have offline MkDocs search and Help > User Guide;
  no new application widget, runtime dependency, or implicit network fallback
  is added. Repository-aware agents can run the script when authorized to read
  the checkout, or navigate the included static `llms.txt`/HTML otherwise.

Example from a Python 3.10 repository checkout:

```powershell
.\.venv\Scripts\python.exe scripts\search_user_guide.py "RAW14 stride" --json
.\.venv\Scripts\python.exe scripts\search_user_guide.py "Difference unavailable" --limit 3
```

The JSON is an interface for assistive workflows, not a persisted schema or
external service API. Do not rely on numerical ranking scores or infer an
answer when no authoritative page matches. Current user-facing statements
must not be inferred from roadmap/deferred implementation documents.

## Ask PixelScope evaluation — not implemented

The shipped offline MkDocs search already covers the installed user's
documentation lookup. A separately labeled Ask PixelScope panel would add
UI surface, answer grounding/quality obligations, and potentially model-service
security/maintenance requirements. There is no demonstrated need or approved
deployment/provider contract to justify integrating one in this slice.

If future owner validation warrants an Ask experience, evaluate in order:
1. an explicitly invoked local documentation lookup with relevant source links,
   no generated answer or new background service;
2. an optional on-device question-answer layer only if there is a clear
   validated quality benefit and bounded model/runtime resources;
3. an external provider/RAG integration only with separate owner approval,
   network/access/privacy threat modeling, provider credentials owned by an
   approved boundary, explicit user consent for every transmitted context,
   conservative failure/unknown behavior and source-linked answers.

No future service may silently read or upload local image data, RAW metadata,
source paths, settings, credentials, Remote IQA inputs/results or user sessions.
Help > User Guide must continue working without the network or an AI service.
New protocols such as MCP, `llms-full.txt`, or hosted APIs require a specific
consumer contract and separately reviewed rollout; names alone are not grounds
for adopting a framework or storing another copy of documentation.

## Validation and scope

`tests/unit/test_user_guide_agent_search.py` covers source/line/route
provenance, deterministic ordering, fenced-code exclusion, screenshot-notes
exclusion, Unicode, JSON, empty results and bounded inputs. Existing
`scripts/check_docs.py` verifies that `llms.txt` lists every canonical
MkDocs navigation route exactly once; the generated-site checker additionally
requires each listed HTML page to exist. Documentation CI runs these checks on
Windows and Ubuntu, full repository Ruff, and the established strict
network-blocked MkDocs build. There is no PySide6 UI, release-format,
authentication, P5/IQA, or P7 deployment change in WP-Help-D.
