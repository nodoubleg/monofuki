---
name: monofuki-design-review
description: Generate Monofuki family-rule reports, illustrated guides, and paired glyph iteration worksheets, retaining requested variants and advisory conflicts.
---

Read [AGENTS.md](../../../AGENTS.md) and the
[family-design workflow](../../../docs/family-design/README.md). Work from verified
font bytes and the actual request; use concise verified handoffs for Light04/Black03,
not production exports with similar names. Do not promote weights or create a new
variant unless the task asks for it.

Use `script_helper/family_design.py generate` with a hash-pinned input manifest
and a request manifest. The workflow document describes schemas and regeneration
commands. Use `beta` only for the explicitly labelled synthetic demonstration.
Keep iteration outputs in a fresh `.font-build/` directory and preserve earlier
artifacts/annotated PDFs. All rendering is headless; do not open Preview or run
Sasa Review. No iCloud staging is implied.

All new design findings are advisory. Propose Greg's requested change even when
it conflicts with a rule; show its actual font in the PROPOSED panel and carry the
rule ID, expected versus observed/proposed values, reason, and open decision into
the same worksheet. `rule_ids` focuses discussion; applicable issues must also appear
automatically, so it cannot be used as a conflict filter. Never silently rewrite a rule, waive an issue, reject a requested
variant, or infer approval to make a report pass. Owner-directed changes may update
rules and current notes intentionally. Distinguish observed geometry,
candidate targets, specific approvals, and open choices. Existing build integrity
checks remain binding.

Use one spacious sheet per character, with approved/current/proposed/previous
locally paired; combine identical approved/current panels and label absent forms.
For the retained Black03 study, keep approved Omega/ae paired with Black02 previous
forms. In subsequent iterations, use the latest actual role/approval evidence. Q and
Pi remain open; the retained foot-tail Q font is unselected. Do not invent feedback.

Regenerate guides from `src/design-rules/family-v0.1.yaml`, not by editing the
generated Markdown/HTML. Run the focused unit tests and `generate --verify`.
Read the JSON evidence, render the HTML/SVG headlessly, inspect the illustrations
and issue text, and report actual scope/unmeasured items. Numerical probes apply
only at their designated sections/angles; ink area is not perceived weight.

For new default-weight revisions, keep `variant: default`; put revision names in
font IDs. The generator checks eligible proposals against current same-context
references. Use `src/design-rules/current-notes.json` as the editable repository record of
settled/current owner choices and intentional exceptions, with brief rationale and
exact scope. Font source implements them; worksheets/markup are evidence, not sole
authority. Do not fabricate approvals or let a raw reference-panel ID imply one.
Current notes can evolve freely; no state machine or per-experiment admin is needed.
An exception remains visible beside the advisory, and changed relevant basis means
reconsideration, never a veto. Use optional `note-basis` only when useful for a settled
choice. Keep intent separate from observed implementation and pending Q/Pi choices.

Use a small scoped commit/checkpoint or separate branch to explore reversibly. Keep
source/rules/notes together when they change together; inspect status and preserve
unrelated work before a deliberate scoped revert. For source in another repository,
record matching checkpoint references and handle the counterpart explicitly. Do not
reset broadly, delete history, or overwrite annotated evidence. Regenerate and verify
all five text outputs after restoring a path.
