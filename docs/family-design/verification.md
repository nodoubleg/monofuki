# Verification — 2026-10-26

The production-font baseline before this task was `354aeb2` on `master`. This record
describes local advisory-tool changes; it is not a live Git-status assertion. No
push, deployment, release, installation, production-font edit, proportional font,
weight promotion, iCloud staging, Preview or Sasa Review is included.

Start with the [guide](example/guide.html), [worksheets](example/worksheet.html),
and [output receipt](example/output-manifest.json). Eight rules cover four numeric
methods/relationships and four visual-review items. Candidate targets are proposals,
not approvals inferred from observed geometry. The original-g note is not a waiver.

## Checks

- Thirty-three focused regression tests pass. They cover section/angle geometry,
  proposed-weight substitution, variant isolation, target consistency, partial
  measurements, missing Unicode coverage, schema/typo errors, font byte snapshots,
  input aliases, complete output preparation, interrupted replacement detection,
  stale worksheets, source receipts, and advisory exits.
- Real-font beta verifies six pinned historical inputs and the synthetic H advance
  example: **22 numeric passes, one synthetic advisory, zero unsupported numeric
  probes, 17 visual-review rows**, exit 0. These are sampled per-input results, not
  whole-font certification. The extra proposal relationship is evaluated explicitly.
- All five generated text outputs are compared by `generate --verify`, including
  the no-request worksheet contract and receipt. Repeated generation in separate
  directories is checked for identical document and synthetic-font bytes.
- All five repository skills pass the skill-creator validator. The implementation
  needs only the existing fontTools environment; no build framework is added.
- A new adversarial reviewer independently reproduced nine initial issue groups
  beyond the first completion review, then retested the fixes and final staged diff.
  See the [fresh review](adversarial-review.md); the earlier
  [completion review](independent-review.md) remains a historical stage record.
- Headless validation covers the ten guide sections, four worksheet sections, and
  additional actual Black03 tall-accent comparisons. Shared em framing encloses
  actual glyph bounds and keeps comparison roles at equal scale. Physical print
  and PDF pagination are not established by desktop rendering.
- Whitespace/local-link checks, private-host-locator scan, existing native-handoff
  regression tests, scoped staging, and source/artifact preservation checks run
  before the local commit. Existing production build scripts/workflows and font
  sources are unchanged; no production font build or publication is needed here.

## Actual geometry, not approvals

| Font | H/n left stems at y=0.20 em | Slash angle to baseline |
| --- | ---: | ---: |
| Light04 | 0.0576171875 em | 64.470933 degrees |
| Regular reference | 0.0830078125 em | 64.009163 degrees |
| Black03 | 0.1455078125 em | 63.340138 degrees |

Ink area is not perceived weight. The synthetic H changes advance from 575 to 615
units at UPM 1024, from 0.5615234375 to 0.6005859375 em. MF-MONO-001 expects n's
575-unit cell; the proposal remains visible with expected/observed values, reason
and open decision. It is a test, not owner feedback. Q/Pi remain open and no new
approval is created. Approved Omega/ae refers only to the retained Black03 forms.

## Preservation and portability

Canonical workbook hashes still match the retained handoffs:

- Black03: `f99137c4b858886886545be0195289787dfb9d12798eb3cedb200e27bf611b49`.
- Light04: `eefe93d5425060418447ec1b6fa237e0bfdb995ac0daaccba470b5c535916538`.

Historic fonts/annotated PDFs and unrelated user files stay untouched. The generated
synthetic font and private absolute input paths remain in ignored local outputs.
Committed examples contain only self-contained HTML, Markdown and JSON, with font
identities/hashes but no host paths. Local memories are not edited. Experimental
artifact/handoff checkpoints were verified to exist; roadmap references are retained
without private host locators or session IDs.

## Reproduce

Use a Python with fontTools and set `MONOFUKI_REVIEW_HISTORY` to the relocated review
input root. Commands and manifest details are in the [workflow](README.md).

```sh
python3 -m unittest discover -s script_helper -p 'test_*design*.py' -v
python3 script_helper/family_design.py beta \
  --history-root "$MONOFUKI_REVIEW_HISTORY" --out .font-build/family-design
python3 script_helper/family_design.py generate \
  --inputs .font-build/family-design/inputs.json \
  --requests .font-build/family-design/requests.json \
  --out docs/family-design/example --verify
```

A valid run returns 0 for design findings. Invalid/stale inputs or output errors
return 2, without downgrading a known design mismatch to a pass. An interrupted
replacement set is detected by verification; regenerate it before review.

## Limits

Current intent is recorded in the repository's lightweight current-notes file. Two
specific choices were imported from verified plain ae/Omega owner markup; Q/Pi remain
open and no owner exception is invented. The selected candidate and current Black03
per-glyph geometry/advance match. No formal approval ledger or per-experiment state
machine is introduced. Intent and recorded implementation are separate.

Intentional exception notes can be displayed distinctly without suppressing rule
advisories. Narrow basis comparisons prompt reconsideration after relevant rule,
glyph/advance/component changes; unrelated font/glyph changes do not stale a note.
This is a comparison aid, not geometric equivalence proof or automatic approval.
Creative proposals remain available with exit 0. Source/rules/notes can be restored
with scoped commits/reverts as documented; no existing experiment was reverted.

Optical judgments, italic/proportional geometry, shaped spacing, canonical
descendants, exhaustive Unicode/Nerd behavior and physical print remain outside
this beta. The advisor route was skipped for this final diff review because review
was owned by the separately requested fresh independent reviewer. Earlier advisor
preflight availability limits are recorded only as historical context.
