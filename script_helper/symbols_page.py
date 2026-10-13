"""Generate the symbols catalogue from the font project's own provenance."""
import html
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DONORS = {
    'iosevka': ('Iosevka Nerd Font', 'https://github.com/ryanoasis/nerd-fonts/tree/v3.5.1/patched-fonts/Iosevka'),
    'noto-symbols2': ('Noto Sans Symbols 2', 'https://github.com/notofonts/symbols'),
    'kreative-square': ('Kreative Square', 'https://www.kreativekorp.com/software/fonts/ksquare/'),
}
CHARTS = {'controls': 'U2400', 'dingbats': 'U2700', 'symbols-b': 'U2B00', 'legacy': 'U1FB00'}


def render_symbols(nerd_directory, coretext_directory):
    catalog = json.loads((nerd_directory / 'character-catalog.json').read_text())
    snapshot = json.loads((coretext_directory / 'coretext.json').read_text())
    assert snapshot['font_sha256'] == catalog['font_sha256'], 'CoreText snapshot uses different fonts'
    assert catalog['unicode_version'] == '18.0.0' and catalog['nerd_fonts_version'] == '3.5.1'
    baseline = []
    for item in catalog['baseline']:
        cp = item['codepoint']
        glyph = ('a' if item['category'].startswith('M') else '') + chr(int(cp, 16))
        status = 'in Monofuki' if item['regular'] else 'uses another font; see the fallback examples'
        baseline.append(f'<span class="repertoire-glyph" title="U+{cp} {html.escape(item["name"])} — {status}">{html.escape(glyph)}</span>')
    icon_groups = {}
    for item in catalog['icons']:
        icon_groups.setdefault(item['group'], []).append(item)
    icons = []
    for group, entries in icon_groups.items():
        tiles = []
        for item in entries:
            cp = item['codepoint']
            label = html.escape(' / '.join(item['aliases']), quote=True)
            tiles.append(f'<span class="nerd-icon" data-codepoint="{cp}" data-icon-search="{label.lower()}" '
                         f'title="U+{cp} {label}" aria-label="U+{cp} {label}">&#x{cp};</span>')
        labels = {'unicode': 'Standard Unicode symbols', 'pom': 'Pomicons', 'pl': 'Powerline', 'ple': 'Powerline Extra',
                  'fae': 'Font Awesome Extension', 'weather': 'Weather Icons', 'custom': 'Custom Icons', 'seti': 'Seti UI',
                  'indent': 'Indentation', 'dev': 'Devicons', 'cod': 'Codicons', 'fa': 'Font Awesome', 'extra': 'Extra Icons',
                  'linux': 'Font Logos', 'oct': 'Octicons', 'md': 'Material Design Icons'}
        icons.append(f'<details class="icon-group"><summary>{html.escape(labels.get(group, group))} <span>{len(entries)}</span></summary>'
                     f'<div class="icon-wall nerd">{"".join(tiles)}</div></details>')
    expected = {(item['codepoint'], variant) for item in catalog['fallback'] for variant in ('regular', 'nerd') if not item[variant]}
    actual = {(item['codepoint'], item['variant']) for item in snapshot['records']}
    assert actual == expected and len(snapshot['records']) == len(actual), 'Incomplete fallback snapshot'
    fallback = []
    for record in snapshot['records']:
        cp, variant = record['codepoint'], record['variant']
        names = ', '.join(record['fonts'])
        result = 'No glyph available in this example' if record['missing'] else 'Drawn by ' + names
        x, y = record['x'] // 2, record['y'] // 2
        fallback.append(f'<article class="fallback-card" data-variant="{variant}" data-codepoint="{cp}" data-fallback-search="{html.escape(record["name"].lower())} {html.escape(names.lower())}">'
                        f'<span class="native-glyph native-{variant}" role="img" aria-label="CoreText rendering of U+{cp} {html.escape(record["name"])}" '
                        f'style="background-position: -{x}px -{y}px"></span><code>U+{cp}</code>'
                        f'<h4>{html.escape(record["name"])}</h4><small>{"Monofuki" if variant == "regular" else "Monofuki Nerd Font"} selected<br>{html.escape(result)}</small></article>')
    additions = json.loads((ROOT / 'script_helper/symbol_additions.json').read_text())['additions']
    ranges = json.loads((ROOT / 'script_helper/terminal_ranges.json').read_text())
    assert len(additions) == len({item['codepoint'] for item in additions}) == 415
    counts = Counter(item['donor'] for item in additions)
    highlights = ('2BB7', '2700', '2B96', '2BD4', '1FB00', '1FBCB', '1FBCD', '1FBFA')
    cards = []
    options = []
    for key, title, first, last in ranges['blocks']:
        group = [item for item in additions if first <= int(item['codepoint'], 16) <= last]
        if not group:
            continue
        options.append(f'<option value="{key}">{html.escape(title)} ({len(group)})</option>')
        tiles = []
        for item in group:
            cp = item['codepoint']
            donor, url = DONORS[item['donor']]
            chart = f'https://www.unicode.org/charts/PDF/{CHARTS[key]}.pdf'
            tiles.append(
                f'<article class="symbol-card" id="u-{cp.lower()}" data-codepoint="{cp}" data-block="{key}" '
                f'data-donor="{item["donor"]}" data-name="{html.escape(item["name"], quote=True)}">'
                f'<span class="symbol-glyph" aria-hidden="true">&#x{cp};</span>'
                f'<a class="symbol-code" href="#u-{cp.lower()}">U+{cp}</a>'
                f'<h4>{html.escape(item["name"])}</h4>'
                f'<a class="symbol-donor" href="{url}">{donor}</a>'
                f'<div class="symbol-actions"><a href="{chart}" title="{html.escape(title)} — Unicode chart">Chart ↗</a>'
                f'<button type="button" data-copy="{cp}" aria-label="Copy U+{cp} {html.escape(item["name"], quote=True)}" hidden>Copy</button></div>'
                '</article>')
        cards.append(f'<section class="symbol-group" data-group="{key}" aria-labelledby="group-{key}">'
                     f'<h3 id="group-{key}">{html.escape(title)} <span class="group-count">{len(group)}</span></h3>'
                     f'<p class="group-range">U+{first:04X}–U+{last:04X}</p>'
                     f'<div class="symbols-grid">{"".join(tiles)}</div></section>')
    previews = []
    for cp in highlights:
        item = next(item for item in additions if item['codepoint'] == cp)
        previews.append(f'<a class="symbol-highlight" href="#u-{cp.lower()}"><span aria-hidden="true">&#x{cp};</span>'
                        f'<strong>U+{cp}</strong><small>{html.escape(item["name"])}</small></a>')
    return {
        '@@ORIGINAL_REPERTOIRE@@': ''.join(baseline),
        '@@ORIGINAL_COUNT@@': str(len(baseline)),
        '@@NERD_REPERTOIRE@@': '\n'.join(icons),
        '@@NERD_COUNT@@': str(len(catalog['icons'])),
        '@@FALLBACK_GALLERY@@': ''.join(fallback),
        '@@SYMBOL_GALLERY@@': '\n'.join(cards),
        '@@SYMBOL_HIGHLIGHTS@@': '\n'.join(previews),
        '@@BLOCK_OPTIONS@@': ''.join(options),
        '@@DONOR_OPTIONS@@': ''.join(f'<option value="{key}">{label} ({counts[key]})</option>' for key, (label, _) in DONORS.items()),
        '@@TESTED_RANGES@@': ''.join(f'<li><span>{html.escape(title)}</span><code>U+{first:04X}–U+{last:04X}</code></li>'
                                   for _, title, first, last in ranges['blocks']),
    }
