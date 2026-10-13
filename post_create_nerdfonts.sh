#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Local builds and CI use the same checksum-verified Nerd Fonts 3.5.1 patcher.
patcher=$(python3 script_helper/fetch_build_dependencies.py nerd-font-patcher)
for style in Regular Italic Bold Bold-Italic; do
    if [[ -f "export/Monofuki-${style}.otf" ]]; then
        fontforge -lang=py -script "$patcher" --no-progressbars --complete \
            --braille rectangle --outputdir export/ "export/Monofuki-${style}.otf"
        fontforge -lang=py -script script_helper/check_nerd_preservation.py "export/Monofuki-${style}.otf" "export/MonofukiNerdFont-${style//-/}.otf"
    fi
    input="export/Monofuki-${style}.ttf"
    hinted="export/Monofuki-${style}-hinted.ttf"
    if [[ -f "$hinted" && "$hinted" -nt "$input" ]]; then
        input="$hinted"
    fi
    if [[ -f "$input" ]]; then
        fontforge -lang=py -script "$patcher" --no-progressbars --complete \
            --braille rectangle --outputdir export/ "$input"
        fontforge -lang=py -script script_helper/check_nerd_preservation.py "$input" "export/MonofukiNerdFont-${style//-/}.ttf"
    fi
done
python3 script_helper/preserve_nerd_font_names.py export/MonofukiNerdFont-*.ttf export/MonofukiNerdFont-*.otf
cp licenses/LICENSE-NerdFonts export/LICENSE-nerd-font
cp licenses/license-audit-nerd-font.md export/license-audit-nerd-font.md

python3 script_helper/bundle_notices.py export
cp src/nerd-policy.json export/nerd-policy.json
python3 script_helper/check_font_names.py export/MonofukiNerdFont-*.ttf export/MonofukiNerdFont-*.otf
