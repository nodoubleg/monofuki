---
name: monofuki-deploy
description: Prepare or publish Monofuki downloads and the specimen site using validated same-run artifacts.
---

Read [website/README.md](../../../website/README.md),
[the workflow](../../../.github/workflows/build-fonts.yml), and
[AGENTS.md](../../../AGENTS.md). Determine whether the task authorizes a local
build, push, Pages deployment, release creation, or font installation; one does
not imply the others. Preserve existing releases and assets unless asked otherwise.

The workflow builds all four regular/Nerd styles, renders native macOS fallback
previews, stages the site from those exact artifacts, records a fresh VHS video,
and publishes Pages from `master`. Never reuse an old-name recording or unrelated
font build. Both download ZIPs need all four styles, licenses, component notices,
source/glyph provenance, and locked input metadata. Build scripts and CI contain
the current commands and expected file list.

Before an authorized publish, check the actual diff and scoped staging, build
results, names, notices, ZIP contents, and source revision. After publishing,
verify the deployment result, `build.json` revision, downloads, and public URLs.
For live-font claims, use browser rendered-font evidence on actual elements,
including nested code spans; a CSS declaration alone is insufficient. The video
is a recording with separate font provenance, not live webpage text.

Report the commit/run URLs and exact checks. Stop or fix a failed deployment
within scope rather than claiming success. No upstream messages or PRs are part
of publishing this personal fork.
