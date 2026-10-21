# Supervised native verification

Linux CI is the canonical font builder. After it succeeds, Greg Mason runs the
native checks on the connected Mac and explicitly submits their results. A
separate Ubuntu workflow validates that evidence, builds the site and recording,
and publishes Pages. No GitHub-hosted Mac, permanent local runner, new credential,
font installation, or terminal-app UI is involved.

## Run the handoff

Use the existing `nodoubleg` GitHub CLI session, Python with fontTools, and the
Mac's Swift toolchain. The Linux build summary gives its run ID. From the current
repository checkout:

```sh
python3 script_helper/verify_on_mac.py check RUN_ID \
  --output /path/to/new/native-verification-directory
python3 script_helper/verify_on_mac.py submit \
  /path/to/new/native-verification-directory
```

The first command accepts only a successful, complete build of current `master`
in `nodoubleg/monofuki`. It downloads the two immutable artifacts for that exact
run attempt, checks their GitHub SHA-256 digests, and fetches the native scripts
from that exact source commit. It runs fallback rendering, tuned placement and
metrics, superscript/subscript visibility, the complete native export visibility
audit, and emoji/cluster checks. Swift's module cache stays in the work directory.
It does not execute code from a pull request or fork.

The second command rechecks the current build and every local input/result. It
pushes only `native-evidence.zip` to the separate `native-verification` branch,
using an ordinary fast-forward commit, and dispatches `Publish verified site`.
The source branch and font artifacts are not rewritten. No release or tag is
created. Keep this work directory until publication is confirmed; it records
the evidence commit and publication run URL.

## Trust and publication gates

This is an owner-supervised attestation, not remote attestation of the Mac.
The authenticated repository owner's explicit submission is the assertion that
the native scripts ran. Hashes bind that assertion to the exact source and files;
they cannot prove execution on their own. The owner already has authority to
change source and publish the repository. No wider set of submitters is trusted.

The publication workflow runs only after an owner dispatch on `master`. It
downloads the fonts again from GitHub and independently validates:

- The repository, workflow, source commit, successful build run and attempt.
- Exact artifact IDs, archive digests, and every extracted input-file hash.
- Native script hashes against the trusted source checkout.
- A retained immutable evidence commit whose tree contains one data bundle.
- All required native steps, reports, style/format coverage and output hashes.
- Actual host version, complete fallback atlases, tuned modes/metrics, visible
  superscript/subscript glyphs, export audit, and emoji/cluster results.

Unknown or corrupt payloads, unsafe archive paths, symlinks, duplicate entries,
extra executables, missing/failed checks, wrong fonts and old attempts fail closed.
Evidence files are parsed as data; the evidence branch is never checked out or
executed. Only trusted source scripts run in CI. Actions uses read-only contents
and artifact access; only the final Pages job receives Pages/OIDC publication
permissions. There is no workflow permission to write source or evidence.

The workflow rechecks current `master` and the successful build attempt immediately
before deployment. As with any deployment, a source push racing the final API
check can leave the just-verified version briefly live; it cannot substitute
unverified bytes. Every deployment and its public `build.json` identify the
actual published source and evidence, never a moving branch label.

The data branch keeps evidence history separate from source. Its compressed
native reports and rendered images add several megabytes per verification; fonts,
Apple font files, executable scripts, credentials and local paths are excluded.
The proof ZIP is also retained as an Actions artifact and published at
`downloads/Monofuki-native-verification.zip`. `native-verification.json` and
`build.json` identify its immutable commit, hashes, Linux run/attempt and Mac host.
Results describe that macOS version; they do not claim iOS or terminal-app testing.

## Failures and retries

- A failed/incomplete Linux build cannot be verified or published. Artifacts
  include the attempt number, so a later attempt cannot silently replace inputs.
- A failed native command leaves diagnostics in `logs/` and cannot be submitted.
  Use a new output directory for another native attempt; partial output is not reused.
- A new source commit or build attempt invalidates the previous proof. Verify
  the new successful artifacts before submitting again.
- A publication failure can be retried through Actions with the same proof if
  its source, build attempt and artifacts remain valid. Re-running all jobs repeats
  full evidence validation and uploads a uniquely named Pages artifact for that
  site attempt. A deploy-only retry reuses the successful site job's exact artifact
  name and reruns the current-source/build-attempt check before deployment.
- Repeating `submit` after a confirmed dispatch finds the existing run instead
  of creating another. An uncertain dispatch is recorded and must be checked
  before any explicit retry. A push is confirmed against the remote ref; it
  never retries with force or silently rewrites another result.
- A rejected concurrent evidence-branch push is safe to retry after inspecting
  its outcome. The next submission fetches the current branch and appends a
  fresh fast-forward commit containing the same validated data.

The Mac must be awake, connected and available for this supervised step. The
previous deployed site remains available while verification is pending.
