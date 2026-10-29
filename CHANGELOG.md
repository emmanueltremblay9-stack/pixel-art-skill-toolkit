# Changelog

## Unreleased — stability hardening

- Add strict JSON parsing with duplicate-key and non-standard constant rejection.
- Bound canvas size, scaled output size, coordinate range, and recursive palette/component references.
- Return concise CLI errors for malformed or unreadable inputs.
- Save JSON and PNG exports atomically.
- Keep invalid GUI edits from replacing the last valid document and report save errors in the editor.
- Add repeatability, invalid-input, CLI, JSON round-trip, and PNG export regression coverage.
- Add a layered inventory-panel example and cross-platform GitHub Actions checks.
- Validate path and polygon point collections before rendering, and preserve the last valid editor document when a newly opened JSON file cannot render.
- Add regression coverage for those invalid inputs, invalid GUI opens, and failed atomic PNG replacement.
- Add a skill-guided Block Breaker GUI second pass with a readable title, labeled target window, regular inventory-slot spacing, and a separated hotbar. The first pass remains available at its original commit.

No release version has been assigned to this work.
