#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"
fontforge -lang=py -script script_helper/assemble_sources.py
mkdir -p export

function generate {
  local source_path=$1
  local output_path=$2

  fontforge - << END
font = fontforge.open("$source_path")

if "$output_path"[-3:] == "ttf":
  layers = font.layers
  for layer_name in layers:
    layers[layer_name].is_quadratic = True

for glyph in font.glyphs():
  glyph.unlinkRef()
  glyph.removeOverlap()
  glyph.round()
  glyph.addExtrema("all")
  if glyph.validate() & 0x8 == 0x8:
    glyph.correctDirection()
  glyph.removeOverlap()
  glyph.round()
  glyph.addExtrema("all")

font.appendSFNTName("English (US)", "Copyright", """Original author:
Copyright (c) 2013-2023, Matthias Tellen matthias.tellen@googlemail.com

Upstream Monofoki modifications:
Copyright (c) 2020-2025, Marvin Dostal

Monofuki modifications: Greg (nodoubleg), 2026.

Additional symbol outlines from Iosevka, Noto Sans Symbols 2, and Kreative Square.
Full copyright notices and licenses are included with the fonts.

Licensed under SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
https://scripts.sil.org/OFL""")

if ("English (US)", "SubFamily", "Bold-Italic") in font.sfnt_names:
  font.appendSFNTName("English (US)", "SubFamily", "Bold Italic")

font.generate("$output_path")
END

}

generate '.font-build/assembled/monofuki-Regular.sfd' 'export/Monofuki-Regular.ttf'
generate '.font-build/assembled/monofuki-Italic.sfd' 'export/Monofuki-Italic.ttf'
generate '.font-build/assembled/monofuki-Bold.sfd' 'export/Monofuki-Bold.ttf'
generate '.font-build/assembled/monofuki-Bold-Italic.sfd' 'export/Monofuki-Bold-Italic.ttf'

generate '.font-build/assembled/monofuki-Regular.sfd' 'export/Monofuki-Regular.otf'
generate '.font-build/assembled/monofuki-Italic.sfd' 'export/Monofuki-Italic.otf'
generate '.font-build/assembled/monofuki-Bold.sfd' 'export/Monofuki-Bold.otf'
generate '.font-build/assembled/monofuki-Bold-Italic.sfd' 'export/Monofuki-Bold-Italic.otf'

# FontForge 2023 can erase Bold superscript/subscript n during quadratic overlap cleanup.
# Reuse its correct OTF outline before hinting or Nerd patching.
python3 script_helper/repair_bold_small_n.py \
  export/Monofuki-Bold.otf export/Monofuki-Bold.ttf \
  --provenance export/export-repair-provenance.json

if [[ "$*" == --hint ]]
then
  ttfautohint export/Monofuki-Regular.ttf export/Monofuki-Regular-hinted.ttf
  ttfautohint export/Monofuki-Italic.ttf export/Monofuki-Italic-hinted.ttf
  ttfautohint export/Monofuki-Bold.ttf export/Monofuki-Bold-hinted.ttf
  ttfautohint export/Monofuki-Bold-Italic.ttf export/Monofuki-Bold-Italic-hinted.ttf

  woff2_compress export/Monofuki-Regular-hinted.ttf
  woff2_compress export/Monofuki-Italic-hinted.ttf
  woff2_compress export/Monofuki-Bold-hinted.ttf
  woff2_compress export/Monofuki-Bold-Italic-hinted.ttf
fi

woff2_compress export/Monofuki-Regular.otf
woff2_compress export/Monofuki-Italic.otf
woff2_compress export/Monofuki-Bold.otf
woff2_compress export/Monofuki-Bold-Italic.otf

cp LICENSE export/LICENSE-Monofuki
cp .font-build/assembled/*-provenance.json export/
cp src/overlays.json export/source-overlays.json
cp src/upstream-decisions.json export/upstream-decisions.json
cp licenses/LICENSE-* export/
cp licenses/NOTICES-symbols.md export/
cp script_helper/symbol_additions.json export/symbol-additions.json
cp script_helper/build_dependencies.json export/build-dependencies.json

python3 script_helper/bundle_notices.py export
python3 script_helper/check_font_names.py export/Monofuki-*.ttf export/Monofuki-*.otf

python3 script_helper/check_visible_glyphs.py export/Monofuki-*.ttf export/Monofuki-*.otf
