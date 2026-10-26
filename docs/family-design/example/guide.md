# Monofuki family design v0.1

Current intent is recorded in [current design notes](../../../src/design-rules/current-notes.json); worksheets are generated evidence, never sole authority. Notes are editable and advisory.

Generated from `src/design-rules/family-v0.1.yaml`. All findings are advisory.

[Illustrated guide](guide.html) · [Evidence report](report.json)

## MF-MONO-001 — Keep the mono cell stable

Sampled spacing glyphs retain the n advance. Combining marks and Nerd icons are outside this probe.

Approval: approved-policy. Scope: `{'width': ['mono']}`. Method: advance. Tolerance: 0.

Greg, 2026-10-26: mono family stays intact. Existing terminal/build contracts remain separate.

## MF-STEM-001 — Compare related upright stems

Compare H and n left stems at y=0.20 em. Proposed absolute difference <=0.015 em; discuss any mismatch rather than forcing equality.

Approval: candidate. Scope: `{'weight': ['Light', 'Regular', 'Black'], 'width': ['mono', 'proportional']}`. Method: stem. Tolerance: 0.015.

New beta probe proposed 2026-10-26; numeric tolerance has no design approval. Measures two filled intervals only.

## MF-WEIGHT-001 — Check the weight progression at a defined section

At y=0.20 em, H left stem should progress Light < Regular < Black, by more than 0.005 em per step. This does not measure perceived weight.

Approval: candidate. Scope: `{'width': ['mono'], 'variant': ['default']}`. Method: weight-order. Tolerance: 0.005.

New beta relationship proposed 2026-10-26; current experimental geometry is evidence, not a requirement.

## MF-ANGLE-001 — Compare the designated slash edges

Compare acute angles to the baseline of the longest straight slash/backslash edges spanning >=0.5 em vertically. Proposed difference <=1 degree. Curved/unsupported geometry is unmeasured.

Approval: candidate. Scope: `{'weight': ['Light', 'Regular', 'Black'], 'width': ['mono', 'proportional']}`. Method: angle. Tolerance: 1.

New beta probe proposed 2026-10-26. Straight Bezier edges require control points within 0.25 font units of chord; no generic angle inference.

## MF-OPTICAL-001 — Review optical rhythm and family identity

Review perceived weight, counters, terminals, joins and recognizability at text and display sizes. Light/Black may need optical differences; no ink-area proxy.

Approval: open. Scope: `{'weight': ['Light', 'Regular', 'Black'], 'width': ['mono', 'proportional']}`. Method: visual. Tolerance: visual only.

Greg, 2026-10-26: beta-test rules alongside final Light/Black review. No universal numeric optical target approved.

## MF-FORM-001 — Keep approved Black forms visibly paired

Show Black03 current approved Omega and ae beside Black02 previous forms when reviewing these characters. Approval is specific to these forms, not every Black03 glyph.

Approval: approved-specific-forms. Scope: `{'weight': ['Black'], 'variant': ['default']}`. Method: visual. Tolerance: visual only.

Current intent: MFD-BLACK-AE and MFD-BLACK-OMEGA in current-notes.json, verified against owner-marked Black02 pages95/96. Approval is plain ae/Omega only; descendant body implementation is family consistency, not separate owner approval.

## MF-CHOICE-001 — Keep Q and Pi choices open

Q and capital Pi remain open design choices. Display current/proposed/previous locally; do not mark a candidate approved or silently choose it.

Approval: open. Scope: `{'weight': ['Light', 'Regular', 'Black'], 'width': ['mono', 'proportional']}`. Method: visual. Tolerance: visual only.

handoff-Black03-20261024.json pending_choices: foot-tail Q unselected; Pi right-foot question pending.

## MF-PROP-001 — Plan proportional spacing independently

Review sidebearings and word rhythm independently of mono advances while retaining family identity. Start Light, then Black, then Regular. No proportional geometry target exists yet.

Approval: open. Scope: `{'width': ['proportional']}`. Method: visual. Tolerance: visual only.

Greg, 2026-10-26 roadmap. Proportional variants are future work, not implemented or promoted by this system.

## Exceptions

```json
[
  {
    "id": "MF-EX-001",
    "rule": "MF-OPTICAL-001",
    "scope": {
      "weight": [
        "Black"
      ],
      "variant": [
        "original-g"
      ]
    },
    "reason": "Black03 original-g alternate changes U+0067 only; accented g descendants retain default drawing. Coverage limitation, not a waiver of review.",
    "approval": "observed-limitation",
    "provenance": "handoff-Black03-20261024.json limits. No new design exception approved."
  }
]
```

Numeric passes cover only the designated samples and sections. Optical review, italic, shaping, full repertoire and proportional geometry are not measured.
