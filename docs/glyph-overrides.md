# Glyph ownership and deliberate upstream updates

`src/overlays.json` is the recipe. `script_helper/build_dependencies.json`
locks the four upstream styles and donor inputs by revision and SHA-256.
`assemble_sources.py` applies these layers in order:

1. The pinned Monofoki source for the requested style.
2. Generated Braille.
3. The explicitly restored same-weight upright arrows in italic styles.
4. The selected donor symbols. Generated/donor collisions stop the build unless
   an exact fingerprint-bound decision adopts upstream or keeps the overlay.
5. Individually authored additions or replacements, guarded by fingerprints.

The arrow and donor steps are disjoint. Authored entries are sorted by glyph
name; duplicate ownership is an error, not last-writer-wins. Bold always uses
its own upstream source. Mononoki is an ancestor, not a competing second base.

## Add or replace an individual glyph

Assemble first. Inspect `.font-build/assembled/glyph-provenance.json` to find
the exact glyph name, Unicode mapping, dependencies, and current record hash.
Characters and glyphs are different: an unencoded component has a glyph name
and ID but a null codepoint. Alternate Unicode records are retained in the
inventory. A changed component can affect inherited composite glyphs without
changing their SFD records; inspect its reference dependents too.

Place exactly one complete `StartChar` through `EndChar` SFD record, including
the final newline, in `src/overrides/<style>/<glyph-name>.glyph`. Keep its glyph
name and primary Unicode mapping. Only these individual authored records are
tracked; merged fonts stay in the ignored build directory.

Add an entry to `authored_overrides`. This is the schema, with explanatory
values rather than a ready-to-run entry:

```json
{
  "style": "Regular",
  "glyph_name": "A",
  "codepoint": "0041",
  "operation": "replace",
  "source": "src/overrides/Regular/A.glyph",
  "source_sha256": "SHA-256 of the authored record file",
  "expected_upstream_revision": "the lock's upstream revision",
  "expected_base_sha256": "SHA-256 of the assembled record before authored overrides",
  "dependencies": []
}
```

Use `operation: "add"` and `expected_base_sha256: null` for a new glyph name;
its codepoint must also be unused, or null for an unencoded component. All
styles must retain identical encoded coverage. An override is style-specific.
The assembler retains replacement glyph IDs and deterministically assigns new
IDs. Do not guess final IDs in an authored record.

Every `Refer` in an authored record needs a dependency entry:

```json
{
  "source_gid": 9000,
  "glyph_name": "custom.component",
  "expected_source_sha256": "SHA-256 of the dependency's source record"
}
```

`source_gid` is the reference ID in the authored file, not the eventual font.
The assembler maps it to the named final glyph and verifies its Unicode value.
For another authored glyph, fingerprint its raw `.glyph` file; otherwise
fingerprint the dependency's assembled record before authored overrides.
This works for unencoded components and references to other authored records,
regardless of manifest order. Missing dependencies, cycles, duplicate owners,
stale source hashes, changed base records, and changed upstream revisions fail.
A replacement may not silently change the existing character mapping.

Compute hashes from the actual UTF-8 record bytes, for example with
`shasum -a 256 src/overrides/Regular/A.glyph`. Update an authored source hash
only after reviewing that edit. Do not refresh expected base or dependency
hashes simply to make a failed build green: compare the upstream changes first.

Reassemble and run the source tests and normal output checks in README.md.
The geometry and terminal-metric checks remain part of the product contract;
an intentional change to those requirements also needs an explicit check/policy
change. No authored override waives the Nerd Font preservation policy.

## Generated provenance

`glyph-provenance.json` lists every glyph in all four assembled styles, including
unencoded components: glyph name/ID, primary character mapping, alternate
Unicode records, dependency names, final record hash, and provider (upstream,
Braille generator, named donor, restored arrow, or authored file). The enclosing
upstream record and build lock identify pinned revisions and hashes.
`source-provenance.json` summarizes unchanged upstream counts and assembled
hashes. `src/upstream-decisions.json` records explicit collision choices; its copy also
ships with the downloads. Both provenance reports ship with regular and Nerd Font downloads. They describe
source assembly; export cleanup and the explicitly allowed Nerd substitutions
are separate transformations recorded by the build scripts and Nerd policy.

## Upstream updates

Keep the `upstream-tracking` branch clean using CONTRIBUTING.md. Deliberately
choose an upstream commit. Before changing the lock, save the old one:

```sh
mkdir -p .font-build
cp script_helper/build_dependencies.json .font-build/before-lock.json
```

Prepare a candidate lock in `.font-build/candidate-lock.json`: update the upstream
revision and all four exact raw URLs, revision fields, revision-specific cache
filenames, and SHA-256 values. Fetch actual bytes to establish hashes; never guess
or disable verification. Keep donor/patcher changes separate from this upstream
review. Preserve the currently assembled sources while creating the report:

```sh
fontforge -lang=py -script script_helper/upstream_conflicts.py report \
  --before-lock .font-build/before-lock.json \
  --candidate-lock .font-build/candidate-lock.json
```

Open `.font-build/upstream-review/specimen.html` for old-upstream,
candidate-upstream, and current-custom SVG outlines, widths and bounds. Read
`report.json` for full record diffs, source/style/codepoint/glyph identity,
reference dependencies, affected composites, and metadata/metrics/layout diffs.
Missing glyphs are explicit. Per-glyph layout changes appear in record diffs.
The narrower `review_upstream.py --before-lock ... --after-lock ...` remains
available for a source-only diff without ownership decisions or visual output.

The report writes `choices.json` with `CHOOSE` for each unresolved conflict.
The maintainer chooses `adopt-upstream`, `keep-overlay`, or `revise-overlay`:

- Adopting upstream omits a colliding donor/generator or removes the authored
  override, retaining the candidate upstream glyph.
- Keeping a donor/generator keeps its outlines with the candidate glyph's
  identity. Keeping an authored override updates reviewed base/dependency
  fingerprints. A removed referenced component cannot be accepted this way;
  explicitly revise the component/reference instead.
- Revising requires an `override` object containing the complete authored-entry
  schema above, pointing to the newly reviewed `.glyph` file and hash. Its style
  and character mapping must match the conflict. A new authored replacement for
  a colliding donor starts from the adopted upstream slot. The candidate glyph
  name is the retained identity; change it explicitly in the authored record if
  upstream uses a different name. Existing source changes that preceded a report
  are captured by that report; changing a snapshotted source afterward requires
  a fresh report. A revision may use a new file without modifying those snapshots.
  Its upstream revision, operation, base hash and dependency hashes are validated
  exactly as supplied; `check` and `apply` never refresh those guards. If another
  ownership choice changes its effective base or component, explicitly revise the
  entry against that chosen source and review the new fingerprint.

The choice file binds to the report fingerprint and each conflict ID. These
include exact candidate and overlay hashes, style, identity, revision, and
changed dependencies. Check the proposed choices without changing authored files:

```sh
fontforge -lang=py -script script_helper/upstream_conflicts.py check \
  --report .font-build/upstream-review/report.json \
  --choices .font-build/upstream-review/choices.json
```

This assembles all four candidate styles in a temporary directory and checks
preservation, references, cycles, ownership and matching coverage. Once choices
have been explicitly authorized, apply them:

```sh
fontforge -lang=py -script script_helper/upstream_conflicts.py apply \
  --report .font-build/upstream-review/report.json \
  --choices .font-build/upstream-review/choices.json
```

`apply` runs the same validation before updating the lock, overlay recipe and
`src/upstream-decisions.json`. It never commits, pushes, installs, or publishes.
All three live destinations are snapshotted even when the old and candidate locks
are separate temporary files. Any later edit rejects the report before writing.
Review the diff. Accepted identical collisions do not require another choice in
a newly generated report; changed candidate/overlay fingerprints or dependencies
trigger review again. Unchanged overrides retain ownership and can bind to a new
revision without asking the same question. A stale report or decision is rejected.
The report/HTML/SVGs stay generated under `.font-build/`.

After applying choices, run assembly, source and conflict tests, all four regular
and Nerd builds, name/terminal checks, and relevant platform rendering checks.
These choices do not waive geometry/metric checks or component license review.
Review changed notices when donors, the patcher, or component versions change.
Report which checks actually ran. The clean tracking branch stays separate from
custom `master`; no upstream post or PR is implied.

## Parameterized tuning exports

The customizer is an additional **export** layer declared by
`src/overlays.json:tuned_export`. The four assembled SFD sources and normal
fingerprinted `.glyph` override mechanism remain the base contract above.
Build complete regular and Nerd base exports first. `build_tuned_fonts.py`
then retains those exact inputs under `export/tuning-base/` and applies the
approved tuning to their exported outlines. It does not save a merged font back
into `src/` or replace upstream SFD records.

`src/tuning/defaults.json` holds the approved configuration. The original
playground's bounded glyph data, component maps and Monofuki-derived alternatives
are retained under `src/tuning/`. Their hashes and the expected source-record
hashes for every referenced glyph are in `src/tuning/provenance.json`. Source drift
fails the native build: command-index masks must be reviewed against new input
geometry before their guards are updated. Bold and Bold Italic always use their
own full base fonts and their own outline data.

`website/tuning/app.js` owns the outline transformations and input validation.
`script_helper/tuning_reference.cjs` executes those same functions without a DOM
for native builds and numerical tests. The browser sends the same full-precision
pen operations to `script_helper/tuning_compiler.py`; both paths use fontTools
4.56.0 and its Python table serializer. No generated font is an authored input.
The default browser and native OTFs are compared from identical base bytes.

The export layer replaces the 323 preview-covered characters without removing
any other character, glyph, or existing mark feature. It changes line metrics to
880/-270, preserves every horizontal advance, and vertically remaps box/block
and Braille graphics from the old 1230-unit cell to the new 1150-unit cell. The
Win clipping metrics enclose the complete font, including untouched tall glyphs.
`tuning-provenance.json` identifies exact base/output hashes, source geometry,
settings, compiler and transform. It accompanies both font families and custom
browser downloads. Source preservation and these export changes are separate
claims and are checked separately.

Contextual optical spacing uses a GPOS `kern` feature with **xPlacement only**.
Shallow chained-context dispatch trees select preceding and following edge
classes, then indexed SinglePos tables position the current glyph. Equal sums
of the two neighbor edges share exact values. Both neighbors stay context, so
partial feature masks and adjacent centers keep the original matching behavior.
Only the root lookup belongs to `kern`; existing mark features remain intact.
It covers the 254 letters/numbers present in the reference data; symbol-run
spacing covers the documented operator set and runs of two through four. The
source formula is rounded to the nearest font unit (at most 0.5 units). The old
0–100 strength range is unchanged. Above 100, a conservative envelope reserves
room for the worst supported neighbor at the old range. Bounds enclose the
selected transformed control points, including a moved or rotated 7 crossbar,
so extra movement cannot add overlap. Existing italic overlaps at the approved 94 setting are retained.
Other Unicode characters and unsupported clusters retain their base behavior.
Applications can disable this feature; the font cannot force a terminal to use
it. CoreText and HarfBuzz evidence is not terminal-app evidence.
