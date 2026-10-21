# Monofuki specimen site

This adapts the paired specimens and explanations of the [original Mononoki site](https://madmalik.github.io/mononoki/) for this fork. The default dark palette comes from Crush's [Charmtone theme](https://github.com/charmbracelet/crush/blob/main/internal/ui/styles/themes.go); the light palette uses darker versions of the same accent hues for legibility.

The `site` job in `.github/workflows/build-fonts.yml` downloads the regular and Nerd Font artifacts from its own workflow run. `script_helper/build_site.py` stages five WOFF2 files, licenses, HTML, and the demo under ignored `_site/`. Generated font and video files are never committed. Only the separate `deploy` job can publish to GitHub Pages, and it runs on `master` outside pull requests.

Asset URLs include content hashes (or the recording's source revision) so a browser cannot keep an older font, video, or poster after a new site build.

To preview locally, download the two artifacts from a successful font-build run, then run:

```sh
python3 script_helper/build_site.py \
  --regular /path/to/regular-artifact \
  --nerd /path/to/nerd-artifact \
  --coretext /path/to/coretext-artifact \
  --revision COMMIT_SHA \
  --build-url https://github.com/nodoubleg/monofuki/actions/runs/RUN_ID
python3 -m http.server --directory _site 8000
```

The site and terminal demo get all three art pieces from `art_pieces()` in `script_helper/terminal_demo.py`. Print them with:

```sh
python3 script_helper/terminal_demo.py --art
```

For the recording, install [VHS](https://github.com/charmbracelet/vhs), `ttyd`, and `ffmpeg`, install the built Monofuki Nerd Font OTFs, and run this from the repository root after staging the site:

```sh
vhs website/demo.tape
```

The tape produces `_site/media/monofuki.mp4`. CI extracts a PNG poster from its final held artwork frame with FFmpeg. It uses deterministic specimen scenes rather than live app sessions. The video has playback controls, a poster, and a text alternative; it does not autoplay. The Nerd Fonts and Unicode versions, font-build revision and per-file SHA-256 values are recorded in `_site/build.json`.

The Symbols page follows the original Mononoki character showcase, Nerd Font
icons, the fork's 415 additions, and characters supplied by native macOS font
fallback. The original list is pinned in `mononoki_repertoire.json`; Unicode
18 script properties omit other writing-system alphabets while keeping Latin,
common punctuation, symbols and private-use icons. Character maps and Nerd
Font names come from the actual build, not hand-maintained icon ranges.

The `coretext` job uses a macOS 26 runner and the same run's OTF files. It
registers those fonts only in its process and renders bare Unicode scalars
into transparent light/dark PNG atlases. The generated records include the
requested font, actual fallback font names, missing-glyph status, host version,
architecture, rendering settings and input font hashes. No Apple font files
or outlines are distributed. The page presents these as macOS fallback examples
and explains that results depend on the visitor's fonts and applications.
Host details and validation history stay out of the visitor-facing copy. Generated catalogues, images and
records remain in ignored staging directories and Actions/Pages artifacts.

To generate a local native snapshot, first export `character-catalog.json`
using `script_helper/export_character_catalog.py`, then run:

```sh
swift script_helper/render_coretext_previews.swift \
  /path/to/character-catalog.json \
  /path/to/Monofuki-Regular.otf \
  /path/to/MonofukiNerdFont-Regular.otf \
  /path/to/generated-coretext
```

All original/addition glyphs and expandable Nerd icon groups remain visible
without JavaScript. Search, filters and copying progressively enhance the page.
All three searches match partial names and code points as the visitor types.
`U+` and `0x` queries match code-point prefixes; for example, `U+1` narrows the
added symbols to the supplementary-plane entries. Icon names accept the `nf-`
prefix, and spaces, hyphens and underscores are interchangeable. Each search
filters only its own catalogue.

The download ZIPs are built from the same font artifacts as the site and contain all four styles plus exact component notices and provenance. Historical Monofoki releases are preserved separately.

The WordArt header is a path-only SVG generated from the built Monofuki Bold
font with `script_helper/generate_wordart.py`. It uses the site's palette and
ships at `website/assets/monofuki-wordart.svg` for the site and README. The
matching fingerprint and provenance JSON files identify the actual font used.
Regenerate it after relevant letterform changes; it does not rely on an installed
font or browser font fallback.

## Customizer and playground

`customize.html` is staged from `website/tuning/template.html`, its application
and editor source, and the locked reference data in `src/tuning/`. It starts and
resets to the approved configuration. The five alternative groups (g, q, zero,
7 and linked braces) remain independently selectable, including original forms.
Individual body/gap/tail controls and strengths 0–400 are compiled into the
selected download. The floating editor, collapsible picker and JSON import/export
are retained. Preview text is reset on import and is not sent to the compiler.

A worker downloads the same-run complete regular/Nerd base fonts and a pinned,
self-hosted Pyodide runtime on demand. It verifies base and notice file hashes,
then runs the shared fontTools compiler locally. Each ZIP contains four styles in
OTF, TTF and WOFF2, exact component notices, the selected settings and provenance.
There is no service endpoint, account, upload or paid infrastructure. The first
build loads roughly 14 MB of compiler assets plus full base fonts; compilation
can take a minute or longer on slower or busy machines. Progress identifies
each style and format, and Cancel stops the worker. Default prebuilt ZIPs remain
available without the compiler. WOFF2 uses lossless Brotli quality 9: decoded
font tables match maximum compression, with a modest size increase and much
shorter encoding time.
Custom family names include a configuration hash so distinct choices can coexist.
Native default TTFs additionally have separately named autohinted exports; browser
TTFs are unhinted on changed glyphs and are identified separately in the ZIP.

`playground.html` uses real WOFF2 files, not SVG glyphs. It has editable code,
prose, symbol/emoji and spacing samples; four styles; size/leading controls; a kern
toggle; and an optional four-style comparison. A successful browser build writes
all four webfonts and their profile ID to IndexedDB in one transaction. The playground can load that
local build. Initial leading is exactly 1150/1024 em, retaining the 1:2 cell
ratio; the Leading Reset button restores it after free leading adjustments.
Samples stay in the tab. Browser storage failure does not prevent
the font download.

The CI build validates all four regular/Nerd styles and all 32 alternative
profiles before staging the site. Native checks include:

```sh
.font-build/tuning-python/bin/python script_helper/build_tuned_fonts.py
.font-build/tuning-python/bin/python script_helper/test_tuning.py --all-profiles
.font-build/tuning-python/bin/python script_helper/test_spacing_safety.py
.font-build/tuning-python/bin/python script_helper/test_spacing_masks.py
.font-build/tuning-python/bin/python script_helper/test_woff2_compression.py
node script_helper/test_site_ui.cjs
fontforge -lang=py -script script_helper/check_terminal_glyphs.py --tuned export/Monofuki-*.otf
swift script_helper/check_tuned_coretext.swift export/Monofuki-*.otf > .font-build/tuned-coretext-proof.json
```

Rebuilding from the saved same-run bases uses `build_tuned_fonts.py --from-base`.
It rejects accidentally tuning an already tuned output. Full rebuilds recreate
base fonts through the normal scripts first. The source contract and spacing
scope are documented in `docs/glyph-overrides.md`. Browser and operating-system
rendering must be checked before publication; static tests alone do not prove
interactive layout or terminal support.
