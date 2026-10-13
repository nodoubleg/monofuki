# Monofuki agent guide

Monofuki is a personal fork of datMaffin/monofoki, based on Mononoki. Keep the
copy direct and personal, with no universal compatibility promises. Preserve
upstream credit, legal notices, Reserved Font Names, and component attribution.

- `master` owns custom work. `upstream-tracking` stays clean and moves by
  explicit fast-forward updates. Upstream topics start there; see CONTRIBUTING.md.
  Do not post, send upstream PRs, publish, or install fonts without task authority.
- Read [the source contract](docs/glyph-overrides.md) before changing glyphs.
  `src/overlays.json` and individual `src/overrides/` records are authored inputs;
  the dependency lock pins imported sources. Never regenerate Bold from Regular.
- `.font-build/`, `export/`, and `_site/` are generated and ignored. Do not commit
  merged fonts or replace upstream source records through a full-font save.
- Preserve unrelated local edits. Prefer checks appropriate to the change;
  distinguish source preservation, binary checks, and actual rendered-font evidence.
  State skipped checks and platform/toolchain limits honestly.
- Ship exact component notices and source/glyph provenance with fonts and site.
  Imported components retain their own terms; do not claim every icon is OFL.

Focused workflows in `.agents/skills/` cover building, authored glyph changes,
locked input updates, and release/site deployment. README.md and the actual
scripts are the source of truth for commands; skills do not grant new authority.
