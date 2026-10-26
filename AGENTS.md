# Monofuki agent guide

Monofuki is a personal fork of datMaffin/monofoki, based on Mononoki. Keep the
copy direct and personal, with no universal compatibility promises. Preserve
upstream credit, legal notices, Reserved Font Names, and component attribution.

- `master` owns custom work. `upstream-tracking` stays clean and moves by
  explicit fast-forward updates. Upstream topics start there; see CONTRIBUTING.md.
  Do not post, send upstream PRs, publish, or install fonts without task authority.
- Read [the source contract](docs/glyph-overrides.md) before changing glyphs.
  `src/overlays.json` and individual `src/overrides/` records are authored inputs;
  the dependency lock pins imported sources. Never regenerate Bold from Regular.
- `.font-build/`, `export/`, and `_site/` are generated and ignored. Do not commit
  merged fonts or replace upstream source records through a full-font save.
- Preserve unrelated local edits. Prefer checks appropriate to the change;
  distinguish source preservation, binary checks, and actual rendered-font evidence.
  State skipped checks and platform/toolchain limits honestly.
- Ship exact component notices and source/glyph provenance with fonts and site.
  Imported components retain their own terms; do not claim every icon is OFL.

Focused workflows in `.agents/skills/` cover building, authored glyph changes,
locked input updates, release/site deployment, and family-design reviews/worksheets.
README.md and the actual scripts are the source of truth for commands; skills do not grant new authority.

## Family-design beta and experimental weights

Read [the family-design workflow](docs/family-design/README.md) for advisory rules,
illustrated guide generation and paired iteration worksheets. The authoritative
source is `src/design-rules/family-v0.1.yaml`; regenerate its Markdown/HTML and
report rather than editing generated examples. Keep observed geometry separate
from candidate requirements, specific approvals and open choices.

All new family-design violations/warnings are advisory during this beta. Propose
requested glyph changes even when they conflict; worksheets must show the relevant
rule ID, expected versus observed/proposed result, reason and open decision. Never
silently waive/rewrite rules, reject requested variants, or infer design approval.
Existing build integrity, security, provenance and publication checks stay binding.

Production was `354aeb2` when this workflow was introduced (2026-10-26).
Light04 and Black03 are experimental local artifacts, not promoted production
weights. Use the verified inputs and concise handoffs described in the workflow;
do not substitute similarly named production exports. Preserve annotated PDFs and
previous artifacts. Keep approved Black Omega/ae current-versus-previous forms
paired; Q and Pi choices remain open. Use spacious individual-character sheets
with approved/current/proposed/previous clearly labelled and locally paired.

Render headlessly; do not open Preview or run Sasa Review. No iCloud staging is
implied. The [roadmap](docs/family-design/roadmap.md) records website polish,
family-spec beta alongside Light/Black final review, later beta promotion, then
proportional Light, Black, Regular. Keep mono intact; do not implement proportional
variants or promote experimental weights without a task asking for that work.

Current design intent and intentional exceptions live in
`src/design-rules/current-notes.json`, not agent memory or worksheets alone. Font
source implements the choice; markup/proofs are evidence. Keep notes brief and
editable, with rationale and exact glyph/weight/width/variant scope. Record only
actual owner choices; keep proposal/intent separate from implementation. Experiments
may conflict freely. Reconsideration notes and intentional exceptions remain advisory.
Do not add an approval state machine or per-experiment paperwork. Use scoped commits
or a branch/checkpoint for reversible paths, keeping source/rules/notes synchronized
when reverting. Preserve history, annotated evidence and unrelated work; no blanket
reset or deletion authority is implied. See the workflow for separate source repos.
