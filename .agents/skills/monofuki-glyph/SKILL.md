---
name: monofuki-glyph
description: Add or replace a Monofuki glyph or unencoded component with explicit ownership and drift checks.
---

Read [the glyph contract](../../../docs/glyph-overrides.md) and
[AGENTS.md](../../../AGENTS.md). Inspect the generated glyph inventory before
choosing a Unicode character or glyph name; unencoded dependencies are glyphs too.

Use the existing Braille/donor recipe for its intended additions, or an individual
`src/overrides/<style>/<name>.glyph` and `authored_overrides` entry for authored
changes. Match the implemented schema exactly. Pin the source file, expected
upstream revision, expected pre-override base record, and every named dependency.
Keep imports out of authored source. Preserve all four upstream styles.

Review why an existing fingerprint changed before updating it. Dependency IDs
in authored records are remapped by name; manifest order cannot resolve duplicate
ownership. Check affected composites as well as the edited glyph. New encoded
characters require matching coverage across styles. Preserve donor licenses and
attribution, including source/transformation provenance.

Assemble and run source-preservation tests, then build/check affected outputs.
An intentional terminal geometry change needs an explicit policy/check update;
do not disable failures merely because an override is declared. Report actual
source and rendered effects separately. Do not install or publish unless asked.

For family-design iterations, use `monofuki-design-review` to evaluate the actual
proposed font and make paired worksheets. All new family-design issues are advisory:
retain a requested variant even when it conflicts and visibly report the rule ID,
expected versus proposed/observed result, reason and open decision. Do not silently
waive/rewrite a rule or infer approval. This does not relax existing source/build
integrity checks. Light04/Black03 remain experimental until separately promoted.
