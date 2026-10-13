---
name: monofuki-build
description: Build and verify Monofuki source assembly and all four regular or Nerd styles.
---

Read [README.md](../../../README.md) and [AGENTS.md](../../../AGENTS.md).
Run commands from the repository root. Install the documented dependencies or
use `nix-shell`; do not assume the host Python has fontTools.

For source changes, assemble, rerun `assemble_sources.py --check`, and run
`fontforge -lang=py -script script_helper/test_source_preservation.py` and
`fontforge -lang=py -script script_helper/test_upstream_conflicts.py`.
Build all four styles with `./create_font.sh --hint`, then
`./post_create_nerdfonts.sh`. The scripts enforce font names, fingerprints,
upstream preservation, component notices, and the explicit Nerd policy.
Run the terminal glyph and Unicode-data checks documented in README.md.

Check generated `source-provenance.json` and `glyph-provenance.json` alongside
fonts. An inherited composite may render differently if an explicitly authored
component changed, even when its source record is unchanged. Report exact input
revisions, checks, and failures. FontForge/toolchain versions can affect exports;
input pinning does not establish bit-for-bit binary reproducibility.

Keep all output under ignored build directories. Building does not authorize
font installation, committing generated fonts, uploading, or publishing.
