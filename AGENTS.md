# Monofuki Agent Guide

This is Greg’s personal fork of datMaffin/monofoki, originally based on Mononoki.
Preserve upstream attribution, Reserved Font Name notices, and component licenses.

## Sources and builds

- `src/overlays.json` is the authored recipe; do not commit imported outlines.
- `script_helper/build_dependencies.json` pins upstream SFDs, donors, and notices.
- `script_helper/assemble_sources.py` writes ignored `.font-build/assembled/`.
- `./create_font.sh --hint` assembles and exports all four original styles.
- `./post_create_nerdfonts.sh` patches regular exports and checks the explicit policy.
- `src/nerd-policy.json` lists allowed glyph substitutions and metric changes.
- `export/`, `.font-build/`, `_site/` are generated, untracked output.
- Python 3 with fontTools, FontForge, woff2, curl, and optionally ttfautohint are needed.
- `nix-shell` supplies a development environment; there is no flake.

Do not regenerate upstream Bold from Regular. Source records and source line
metrics must remain unchanged apart from the explicit family-name/count fields.
Export cleanup is separate from source preservation. Never overwrite cached
upstream sources or run full-font saves over authored recipes.

## Checks

Run assembler `--check`, Braille `--check`, donor-symbol `--check`, Unicode-data
validation, `check_terminal_glyphs.py`, and `check_font_names.py` on outputs.
The Nerd script checks every protected outline/advance against its exact input.
Bundle all component notices for both archives and the website.

## Git and site

`master` is the custom project; `upstream-tracking` mirrors datMaffin/master via
explicit fast-forward updates. Upstream topics branch from the latter. See
CONTRIBUTING.md. Preserve unrelated uncommitted work.

The website is staged by `build_site.py` from same-run fonts and CoreText assets.
Its code samples must inherit the intended font even inside nested `code` tags.
Browser work for this task belongs on the cloud computer, not local Chrome.
