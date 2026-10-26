# Fresh independent adversarial review — 2026-10-26

**Disposition: accepted for a scoped local commit. No remaining blocker found in
this v0.1 scope.**

A new reviewer inspected the actual working tree and final 23-file staged diff,
independently of the implementation agent and earlier completion reviewer. This
was an adversarial correctness and robustness review, not a security scan. Source
access was read-only. Adversarial mutations used temporary copies and fixtures;
production fonts, historical review artifacts and unrelated user files were not
edited by the reviewer.

## Findings corrected and independently retested

1. **Input preservation:** output symlinks could overwrite an input font. Direct,
   symlink and hardlink aliases of protected fonts, rules, notes and source manifests
   are now rejected before writes; source bytes remain unchanged.
2. **Proposed relationships:** weight ordering previously considered current fonts
   only. Each eligible proposal now gets a substitution result against same-context
   current anchors, with its identity and any advisory visible on the worksheet.
3. **Stale artifacts:** no-request generation could leave obsolete proposal sheets
   behind. Every run now manages five text files, including an explicit empty-request
   worksheet and a source/output receipt. Stale or interrupted sets cannot pass
   verification against the current inputs.
4. **Rule consistency:** weight ordering previously measured hardcoded H even when
   another target was declared. It now honors the configured target, and typed
   method-specific validation rejects unsupported configuration before writes.
5. **Clipping:** fixed viewports clipped actual accented glyphs. Shared em-based
   frames now enclose actual bounds and preserve comparison scale across UPMs.
   The reviewer checked bounds for all 1,890 encoded Black03 glyphs; this was a
   framing check, not an exhaustive glyph-design audit.
6. **Partial coverage:** one missing target previously discarded known measurements
   and conflicts. Partial observations and detected breaches now remain visible,
   with missing targets recorded separately. A font without Unicode cmap coverage
   remains cleanly unmeasured rather than producing a traceback.
7. **Schema errors:** omitted metadata, malformed structures, duplicate keys/IDs,
   invalid scopes and misspelled proposal fields could fail unclearly or silently
   omit work. They now return clean operational errors before writes.
8. **Verified bytes:** hashing and reopening fonts separately could mix a reported
   digest with rebuilt geometry. Parsing, measurements and drawings now share one
   verified byte snapshot; a controlled rebuild simulation confirms the binding.
9. **Portability:** reusable documents and committed examples now exclude private
   host locators. The production-font commit is identified as a historical baseline,
   rather than embedding a soon-stale live checkout/status claim.

The lightweight current-note addition received a further adversarial pass. Three
additional issues were corrected: an H-only exception could label an unrelated Q
finding as excepted; malformed note scope types could traceback; and a recorded
choice lacking optional basis could be falsely labelled unrecorded. Interpretations
are now scoped by font and character, malformed notes fail cleanly, and recorded
intent remains recorded while any basis concern is shown separately.

The root also corrected cross-process set iteration order in note mappings and added
a hash-seed regression. Independent real-font runs confirmed deterministic outputs.

## Independent acceptance evidence

- All **33 focused tests** pass, including the cross-process hash-seed test.
- Original failing reproductions were rerun and now exhibit the intended behavior.
- Valid design conflicts, unsupported geometry and reconsideration remain advisory;
  proposals and their expected/observed/reason/open-decision text stay visible.
- A controlled interruption during file replacement leaves the previous completion
  receipt and a detectably incomplete set. Preparation failures preserve old files;
  regeneration repairs the set and restores all receipt hashes.
- Separate real-font beta processes using different hash seeds and output directories
  produced identical five text outputs and identical synthetic font bytes. Each run
  reported 22 numeric passes, one labelled synthetic advisory, zero unsupported
  numeric probes and 17 visual-review rows, with exit 0.
- Generated examples pass `generate --verify`. Final index/worktree contents match;
  staged whitespace and local links pass. The 23-file staged set contains no font,
  PDF or screenshot binary and no private host locator. The unrelated untracked PDF
  remains outside the index and retains its original digest.
- Actual retained markup pages 95/96 and their PDF digest were independently checked.
  They support only the plain ae and Omega selections. Candidate-versus-Black03
  decomposed outlines and advances match exactly for those two characters; unmarked
  descendants do not inherit owner approval, and Q/Pi remain open.
- The reviewer inspected affected headless renders for the tall accent, paired Omega
  choice and explicitly synthetic exception/reconsideration display. Font identities,
  proposal/reference roles, complete accents and scoped issue text were readable.
  The root owns the broader 17-section visual pass and aggregate native-handoff checks.

## Current-note model and limits

The repository current-notes file is an editable record of current intent, brief
rationale and exact glyph/weight/width/variant scope. It is not an immutable ledger
or per-experiment approval state machine. Intent is separate from recorded
implementation. Optional narrow basis comparisons prompt reconsideration after
relevant rule, outline, advance or component changes; they never veto a proposal or
require an approval transition. Unrelated glyph/font and editorial rule changes do
not invalidate the recorded basis. An intentional exception remains distinct beside
the numerical advisory and never suppresses it or converts it to a pass. No real
approved exception was fabricated for the demonstration.

Optical judgment, italic/proportional geometry, exhaustive repertoire/shaping checks,
physical print, PDF pagination and production font builds remain outside this
review. Candidate tolerances are not approved design standards, and ink area is not
perceived weight. No production weight promotion, push, publication or release is
part of this acceptance. The root owns the final scoped local commit.

Reviewed implementation snapshots:

- `script_helper/family_design.py`: `defc5fc3aefa017f86252bd66ac2f63b8a7dfe9ff5dadbea7fd85b0d9bd9808d`
- `script_helper/design_notes.py`: `d7eca4c031b2f65866b04dd5d07c249f120609bc93a6313a903e7d4f16f87237`
- `script_helper/test_family_design.py`: `a6c9e43c85c5f58c9f417982207f0e5c6a33b8299d08bf790a15a112e0cc9156`
- `script_helper/test_design_notes.py`: `fac7b21d14bb7ec9f4188c9a277d31d9df5de2df3abfc99e086685a3ecd4657b`
