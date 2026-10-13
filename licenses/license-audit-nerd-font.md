# Imported font and icon notices

Monofuki is derived from Monofoki and Mononoki under their retained SIL OFL
notices. Imported components retain their own copyright and license terms.
This document does not relicense every icon as OFL or claim a blanket legal
compatibility determination.

`script_helper/build_dependencies.json` pins input bytes and source revisions.
`script_helper/bundle_notices.py` produces `THIRD-PARTY-NOTICES.txt`, individual
notice files, and `component-provenance.json` for both regular and Nerd builds.
The site serves the same notice bundle beside its fonts.

The complete Nerd Fonts 3.5.1 patcher archive is checksum-verified. Its component
LICENSE/OFL files and READMEs are retained, including existing modifications.
Supplementary exact-version notices cover Hack 3.003 (Source Foundry MIT and
Bitstream Vera), Devicons, Seti UI, IEC Power Symbols, Codicons, and Font Logos.
Files without a component-specific license in that archive use Nerd Fonts’
supplied default MIT declaration; the upstream source table and links are
included, not replaced with a guessed copyright holder.

Specific details that must survive packaging:

* Font Awesome is the SVG-derived 6.5.1.custom2 remix, also containing the
  7.3.1 solid fa-volume icon. Retain its CC BY 4.0 notice and remix README;
  do not relabel that OTF as the upstream prebuilt OFL font.
* Codicons 0.0.45 carries CC BY 4.0 plus the appended Jason Long Git Logo
  attribution under CC BY 3.0. Preserve the complete tagged license. The
  imported range includes terminal-git-bash at U+EC71.
* Nerd Fonts’ Material Design README records its U+F1522 repair. Preserve it
  with the Apache 2.0 license.
* The pinned Font Logos binary reports 1.4.0 although the glyph README says
  1.3.0. The exact 1.4.0 source LICENSE is the Unlicense and is bundled.
* `extraglyphs.sfd` identifies Hack 3.003. Include both license sections,
  not only a generic MIT label.

Monofuki selects, scales, positions, and merges donor glyphs, generates
Braille, changes the family name, and optionally applies Nerd Fonts’ complete
patch set. The per-codepoint donor manifest and input hashes are bundled.
No icons are silently removed to simplify these notices.

Before distributing changed inputs, verify the complete applicable notices,
source/version attribution, and modification record again. Missing files or
hash mismatches fail packaging. This inventory documents supplied terms and
provenance; it is not a substitute for resolving any new conflicting terms.
