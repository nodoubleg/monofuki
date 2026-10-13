---
name: monofuki-update-inputs
description: Deliberately update pinned upstream, donor, patcher, or notice inputs and review drift.
---

Read [CONTRIBUTING.md](../../../CONTRIBUTING.md) and
[upstream update instructions](../../../docs/glyph-overrides.md#upstream-updates).
Preserve local work and inspect current branches/remotes before changing them.

`upstream-tracking` follows datMaffin/master by explicit fast-forward only.
`master` is custom. Tracking updates never change the build lock automatically.
Monofoki is the one base; do not merge Mononoki as an equally ranked second base.
An upstream contribution starts from the clean branch, and posting needs authority.

Save the old lock, choose exact revisions, fetch actual bytes, and update URL,
revision, cache filename, and SHA-256 together. Use `upstream_conflicts.py report` to compare old upstream, candidate upstream,
and current custom glyphs. Review its JSON and side-by-side SVG specimen. Ask
the maintainer to choose unresolved ownership; do not select automatically.
Run `check` on explicit choices before authorized `apply`. The linked guide has
the exact commands and choice schema. Accepted choices bind to fingerprints;
changed sources, dependencies or candidate glyphs must trigger fresh review.
Use `review_upstream.py` only when a source-only diff is enough.

For donor or Nerd patcher changes, review component versions, modifications,
licenses, and complete notices too. Run assembly/source tests and regular/Nerd
output checks; compare relevant rendering and document toolchain limits. Never
bypass a hash check, silently reset a diverged tracking branch, or auto-merge into
custom master to clear a failure.
