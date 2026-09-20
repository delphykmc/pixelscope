# Vendored offline-search asset

- **Package:** iframe-worker, version 1.0.4
- **File:** `iframe-worker-1.0.4.js` (unaltered published `shim/index.js`)
- **Upstream source:** https://github.com/squidfunk/iframe-worker/tree/1.0.4
- **Published package URL (provenance only; not used in builds):** https://unpkg.com/iframe-worker@1.0.4/shim/index.js
- **SHA-256:** `e8e412dbcfea9b7e31b5ffa288d7b6035915e714c542f4176a0cdbe262fc9609`
- **License:** MIT; see `iframe-worker-LICENSE.txt`.

The asset is checked in deliberately. Material's offline plugin respects the existing
`iframe-worker` polyfill and does not inject the default extensionless CDN URL.
Avoid automatically fetching or updating it during documentation builds. Verify its
digest before shipping a changed copy. Neither the end-user website build nor the
PixelScope executable is permitted to fetch the package from the CDN.

Material's optional Mermaid support is not used by the current User Guide.
Do not add Mermaid diagrams without first vendoring any newly required assets and
revalidating a cold-cache build with network access blocked.
