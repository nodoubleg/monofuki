# Monofuki family design v0.1

An advisory beta for reviewing Light04 and Black03 alongside family rules. The
[authoritative source](../../src/design-rules/family-v0.1.yaml) uses the JSON subset
of YAML 1.2, so the existing fontTools environment needs no additional parser.
Edit it with valid JSON syntax, not general YAML syntax or comments.

Start with the [illustrated guide](example/guide.html) and
[paired worksheets](example/worksheet.html). The self-contained HTML uses actual
verified font outlines. The [Markdown guide](example/guide.md),
[JSON evidence](example/report.json), and [output receipt](example/output-manifest.json)
come from the same rules, input metadata, requests and generator revision.
H is a labelled synthetic conflict demonstration, not owner feedback. Q is an
existing unselected foot-tail candidate. Omega and ae pair approved Black03
experimental forms with Black02 previous forms; that specific approval does not
promote a weight or approve every glyph in it.

## Policy and authority

Every new design result is advisory: pass, advisory, unmeasured, or visual-review.
A valid run exits **0 even when it finds a violation or unsupported geometry**.
Malformed or changed inputs, invalid configuration, stale documents under `--verify`,
and generation failures exit 2 as operational errors. This tool is not a build or
publication gate. Existing integrity, provenance, preservation, security and native
publication checks remain in force.

Retain a requested conflicting drawing and show the rule ID, expected result,
observed/proposed result, reason and open decision on its worksheet. No rule rewrite,
waiver, approval, selection or automated rejection happens here. Candidate tolerances
are proposals, not approved standards inferred from current geometry.

## Run and regenerate

Use Python 3.10+ with fontTools, through the documented build environment or a local
virtual environment. On the existing development checkout, `.font-build/python/bin/python`
is available. No GUI, network, Preview, Sasa Review or font installation is needed.
Set `MONOFUKI_REVIEW_HISTORY` to the local root containing the retained Light04 and
Black03 review directories. Private host paths belong in local environment/configuration,
not reusable documents or committed examples.

```sh
python3 -m unittest discover -s script_helper -p 'test_*design*.py' -v
python3 script_helper/family_design.py beta \
  --history-root "$MONOFUKI_REVIEW_HISTORY" \
  --out .font-build/family-design
python3 script_helper/family_design.py generate \
  --inputs .font-build/family-design/inputs.json \
  --requests .font-build/family-design/requests.json \
  --out docs/family-design/example
python3 script_helper/family_design.py generate \
  --inputs .font-build/family-design/inputs.json \
  --requests .font-build/family-design/requests.json \
  --out docs/family-design/example --verify
```

`beta` verifies six historical font hashes in
[beta-inputs.json](../../src/design-rules/beta-inputs.json), then generates a seventh,
**synthetic** Black03 copy with only H advance increased by 40 units in its ignored
output directory. Current Light04/Black03 hashes were verified against retained
reproducibility reports; other references are observed inputs, not universal design
requirements. Supply a relocated history root without altering hashes. Do not update
hashes merely to silence a mismatch. Historical fonts and annotated PDFs stay read-only.

## Another iteration

Put manifests and normal iteration outputs in a fresh ignored directory. Input JSON
has a nonempty `fonts` array and optional textual `provenance`. Each font entry has
exactly `id`, `path`, `sha256`, `weight`, `width`, `role`, and `variant`:

- `id`: unique nonblank review identifier, distinct from reserved ID `family`.
- `path`: absolute or relative to the input manifest. Local manifests may contain
  private locators; they are not copied into generated public reports.
- `sha256`: hash of actual bytes, 64 lowercase hexadecimal characters. The tool
  reads each font once, checks those bytes and measures/renders that same snapshot.
- `weight`: `Light`, `Regular`, or `Black`; `width`: `mono` or `proportional`.
- `role`: `current`, `previous`, `proposed`, or `alternate`.
- `variant`: design alternative, such as `default`, `q-foot`, or `original-g`.
  A normal next default-weight proposal **keeps `variant: "default"`**. Put its
  revision in `id`, not `variant`, or default-scoped rules will not apply.

Metadata is a declaration by the manifest author, not font-name recognition or a
design approval. Use verified handoffs and actual bytes to identify a font.
Missing metadata, unknown keys, wrong types and duplicate JSON keys are input errors;
they cannot silently discard proposals or skip a variant scope.

Request JSON has `title`, `notice`, and an `items` array. Each item has a single
Unicode scalar `character`, `label`, `request`, `current` font ID and `rule_ids`
array, plus optional `approved`, `proposed`, `previous` font IDs. Empty focus arrays
are allowed. `rule_ids` focuses discussion; applicable nonpass findings for that
character also appear automatically. An unsupported character remains visibly
unmeasured; a known numeric mismatch elsewhere in a partially covered rule is kept.
Copy the actual request in meaning and label tests explicitly. Never invent feedback.

Supply the real proposed font to claim a proposal was evaluated. Missing forms are
labelled; identical approved/current forms share a panel. Comparison panels share a
bounds-aware frame in em units, enclosing actual accents/overhangs while preserving
scale across different UPMs. This is a per-character outline proof, not shaped text.
For the retained Black03 study, keep Omega/ae paired with previous forms and Q/Pi open.
Use the actual latest approved/current/proposed/previous roles in subsequent reviews.

Weight relationships evaluate current references and **each eligible proposal**
substituted for its weight, within the same width/design-variant context. Explicit
worksheet proposals are checked too. Missing or ambiguous other-weight references
produce unmeasured context, not a guessed pass. Concurrent proposals are evaluated
individually against current references; combined multi-weight proposal families are
not inferred. No mono relationship result is attached to a proportional-only item.

## Output consistency and preservation

Every run manages five text files: `report.json`, `guide.md`, `guide.html`,
`worksheet.html`, and `output-manifest.json`. A no-request run writes an explicit
empty worksheet, so an old proposal sheet cannot survive successful verification.
The receipt binds all four document hashes to generator/rules/input metadata/request
content. `--verify` compares all five against current sources without writing.

The CLI rejects output symlinks, source aliases and hard links to input fonts,
manifests, requests or rule files before writes. It prepares the whole output set
first, then atomically replaces each file, writing the receipt last. A preparation
failure leaves prior outputs intact. A process/filesystem failure during replacement
can leave an incomplete set; `--verify` detects it. Regenerate in a fresh directory
rather than treating that set as valid. Keep previous annotated review artifacts.

## Measurements and limits

- **Mono:** sampled `H n 0 Omega ae Q Pi / backslash` advances against n, in em.
  Combining marks, full repertoire and Nerd icons are outside this probe.
- **Stems:** exact line/quadratic/cubic intersections at y=0.20 em, nonzero winding,
  leftmost of exactly two filled intervals for H/n. Ambiguous vertices, tangencies
  or incompatible geometry are unmeasured. Candidate H/n tolerance: 0.015 em.
- **Weight order:** same declared one-character stem section, current/proposed
  Light < Regular < Black, with candidate minimum step 0.005 em. The implementation
  honors the declared target; unsupported targets remain unmeasured.
- **Angles:** designated slash/backslash only, longest straight edge spanning
  >=0.5 em vertically and >=0.15 em horizontally. Bezier controls must lie within
  0.25 font units of the chord. Candidate acute-angle difference: one degree.
- **Visual:** optical weight, counters, rhythm, joins, terminals, resemblance,
  Q/Pi choices and specific Omega/ae comparisons remain human judgments.

Ink area is not perceived weight. No proportional font, italic geometry, shaped-string
spacing audit, descendant audit, exhaustive Unicode/Nerd coverage, physical print or
PDF pagination is established here. Future font/source changes still need their
normal build and rendered-font checks.

## Current design notes and intentional exceptions

[Current notes](../../src/design-rules/current-notes.json) are the editable repository
record of settled/current intent and unresolved questions. Font source implements
that intent. Worksheets, annotated PDFs and handoffs are evidence and generated
review surfaces; they are never the sole authority. This is not an immutable ledger
or an agent memory. Update or replace a note when the choice evolves; Git keeps history.

Each note has `id`, `kind` (`choice`, `approved-exception`, `open-question`), exact
`scope` (`characters`, `weight`, `width`, `variant`), `rule_ids`, a short `note` and
`rationale`. Optional `evidence` references and a plain `implementation` note give
useful context without a transcript or state machine. Record intent separately from
what was applied: choosing a shape does not itself alter source or promote a weight.
Only record a settled choice/exception when the owner has actually made it. Experiments
can conflict freely; notes never veto or force an approval transition.

The initial notes record only plain Black ae and Omega, verified against green owner
markup on retained pages95/96 and exact candidate-versus-Black03 glyph comparisons.
Unmarked accented descendants do not inherit that owner approval. Q and Pi are open;
the foot-tail Q remains unselected. No approved exception is fabricated. Existing
MF-EX-001 in the rule file is a coverage limitation, not an intentional owner exception.

An `approved-exception` note remains visibly distinct beside the numeric advisory;
it never suppresses a finding or turns it into a pass. An optional `basis` captures
the linked normative rule fields and decomposed glyph outline/advance, in em units.
If relevant geometry, a component dependency, rule, or note scope changes, the tool
says **reconsider-note**, still exits 0, and retains the proposal. Unrelated glyph,
font-name or editorial rule-provenance changes do not invalidate that basis. Missing
basis or overlapping notes prompts a manual comparison rather than blocking work.
Historical previous-form comparisons are not treated as changed current intent.

The helper can print an optional basis when settling a choice; it never writes or
approves a note:

```sh
python3 script_helper/family_design.py note-basis \
  --inputs .font-build/family-design/inputs.json --font Black03 \
  --character H --rule-id MF-MONO-001
```

For a separate test record, put global `--notes path/to/current-notes.json` before
`generate`/`beta`. Reports, receipts and verification bind the chosen notes too.
A request manifest's `approved` font ID only supplies a reference panel: without a
matching current choice note, it is labelled an unrecorded reference, not an approval.

## Reversible experiments

Do not add note administration to each exploratory drawing. Keep ordinary experiments
in ignored review output, using a separate branch for a sizeable alternative or a
small scoped commit/checkpoint for a modest one. Before switching paths, inspect
status and preserve unrelated work. Keep authored source, applicable rule edits and
current notes together in the experiment commit when they change together.

To abandon a committed path, review and revert its scoped commit(s), then regenerate
and verify the guide/worksheets from the restored source/rules/notes. A revert commit
preserves history; resolve conflicts deliberately. This is not permission for a
blanket reset, deletion of annotated PDFs, or overwriting unrelated changes. Reverting
source does not erase historical review evidence. If font source lives in a separate
experimental-history repository, retain matching checkpoint references and revert
its counterpart deliberately: a revert here cannot undo a different repository.
No existing experiment is reverted or history deleted by this implementation.


## Extending the specification

Keep stable rule IDs with scopes, targets, supported method, expected result,
tolerance where numerical, provenance, approval state and examples. New methods need
an explicit geometry definition and meaningful fixtures. Preserve candidate/open
states until actual approval exists. Regenerate from YAML, run focused tests and
`--verify`, then inspect the affected illustrations headlessly.

See [verification](verification.md), the [initial completion review](independent-review.md),
and the [fresh adversarial review](adversarial-review.md) for evidence and limits.
