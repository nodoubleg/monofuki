# Additional terminal symbol outlines

Monofuki incorporates only the Unicode glyphs listed in
`script_helper/symbol_additions.json`, with identical upright symbol outlines in
all four styles. Inherited Monofoki source records remain unchanged; export cleanup and the explicit Nerd patching policy are separate steps.
The font inputs, URLs and SHA-256 digests are pinned in
`script_helper/build_dependencies.json`. Donor binaries are downloaded build
inputs; they are not checked into this repository.

* Iosevka Nerd Font Regular from Nerd Fonts 3.5.1, commit
  `b894ea7803af6aade63d60a4381e006098ec9c4d`: first preference when the actual
  Unicode glyph is present. Copyright 2015-2026, Renzhi Li (aka. Belleve Invis, belleve@typeof.net). See
  `LICENSE-Iosevka`, `LICENSE-NerdFonts`, and `license-audit-nerd-font.md`.
* Noto Sans Symbols 2, version 2.008, Google Fonts commit
  `7b6724ac7ececc713e9ba93af309f7520c9a80a3`: remaining semantic glyphs,
  including the missing ribbon arrows and astrological symbols.
  Copyright 2022 The Noto Project Authors. See `LICENSE-NotoSansSymbols2`.
* Kreative Square, version 2026.09.21, Open Relay commit
  `e4b81241e8c7269a91c0bd865cf5c9e7208fbada`: U+1FBCB WHITE CROSS MARK,
  U+1FBCD BLACK SMALL UP-POINTING CHEVRON, and U+1FBFA ALARM BELL SYMBOL.
  Kreative Square copyright (c) Kreative Software 2017-2026 under the Open Font License. See `LICENSE-KreativeSquare`.

The original donor families carry SIL OFL 1.1 notices. Iosevka Nerd Font also incorporates Nerd Fonts components; their notices and terms are bundled separately in THIRD-PARTY-NOTICES.txt.
Their font names are not used as Monofuki's font name. Glyph provenance records
the original code point and geometric transformation for every addition.
Semigraphics fit the complete terminal cell; other symbols keep their aspect
ratio and fit within side bearings. No unrelated private-use icon substitutes
for a Unicode character.

U+2B96 EQUALS SIGN WITH INFINITY ABOVE is derived by reflecting Noto's
U+2BF9 EQUALS SIGN WITH INFINITY BELOW vertically. Its two components retain
their form with their order reversed. This and the three Kreative glyphs were
compared visually with the rendered Unicode 18 reference charts:
[Miscellaneous Symbols and Arrows](https://www.unicode.org/charts/PDF/U2B00.pdf)
and [Symbols for Legacy Computing](https://www.unicode.org/charts/PDF/U1FB00.pdf).

The Braille sources match Nerd Fonts 3.5.1's default 0.6-ratio rectangle grid;
the Nerd Font build uses its actual Braille generator. Unicode assignment,
name, width and emoji-variation data are the final Unicode 18.0.0 UCD files
from <https://www.unicode.org/Public/18.0.0/ucd/>. See `LICENSE-Unicode`.
