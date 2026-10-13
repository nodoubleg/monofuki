# Working on Monofuki

`master` is Greg’s custom Monofuki branch. The `upstream` remote points to
`https://github.com/datMaffin/monofoki.git`; `origin` points to
`https://github.com/nodoubleg/monofuki.git`.

Keep `upstream-tracking` free of Monofuki changes. A separate worktree avoids
switching away from unfinished custom work:

```sh
git fetch upstream
git worktree add ../monofuki-upstream --track -b upstream-tracking refs/remotes/upstream/master
```

Run that setup once. If `upstream-tracking` already exists locally, use
`git worktree add ../monofuki-upstream upstream-tracking` instead of creating
the branch again. To update the clean worktree explicitly:

```sh
git -C ../monofuki-upstream fetch upstream
git -C ../monofuki-upstream switch upstream-tracking
git -C ../monofuki-upstream merge --ff-only refs/remotes/upstream/master
git -C ../monofuki-upstream push origin upstream-tracking
```

If the fast-forward fails, inspect the divergence; do not reset or force-push.
Branch individual upstream fixes from the clean branch, for example
`git switch -c upstream/fix-description upstream-tracking`. Send those topics
to datMaffin/monofoki. Do not use `master` as the base for an upstream PR.
Updating this tracking branch never updates Monofuki’s build inputs: changing
`script_helper/build_dependencies.json` is a separate reviewed step.

## Source changes

Edit the recipe in `src/overlays.json`, the Braille generator, or the explicit
symbol manifest. Imported font outlines belong in the verified input cache,
not in authored source. Rebuild the disposable assembly and run preservation
checks. `src/nerd-policy.json` documents permitted Nerd patcher substitutions;
expand it only after examining the actual glyph and metric changes.

## Historical Mononoki contribution guide

The following is Matthias Tellen’s original guide, retained for attribution
and design context. Its first-person offers and UFO workflow are his, not a
promise or the build workflow of this fork.

<details>
<summary>Original guide</summary>

# How to contribute
Written by original Mononoki author Matthias Tellen

### adding glyphs

One thing you can always do is just ask me to add a glyph. I'll do my best to react to demands, but since I'm doing this in my free time a cannot make guarantees.

If you want to add glyphs yourself: Since my app of choice (glyphs) is closed source and paid, and all open font development seems to happen with fontforge, I created an ufo version of the regular version of the font. Fontforge knows how to handle these.

Please just use this version for contributions. The dimensions of typical elements are:
```              

 _ _ _ _ _ _ _ _ _ _ _ _ _ _ _______  _ _ _ _ _ _ _ 750 _ _ _ _ _ _   ________
                            |       |                                |   ^    |
 _________________________  | _ _ _ | _ _ _ _ _ _ _ 700 _ _ _ _ _ _  |   | 115|
|         ^               | |       |                                |<--+--->| 
|         |77             | |       |                                |   v    |
|         v               | |       |                                 --------
|        -----------------  |       |
|       |                   |       |
| _ _ _ | _ _ _ _ _ _ _ _ _ | _ _ _ | _ _ _ _ ______500  _____________________ 
|       |                   |       |        /      /   |                     |  
|       |                   |       |       /      /    |                     |
|        --------------     |       |      /      /      _____________        |
|                      |    |       |     /      /                    |       |
|                      |    |       |    /      /                     |       |
|        ______________     |        ----      /                      |       |
|       |                   |                 <                       |       |
|   85  |                   |                  \                      |       |
|<----->|                   |        ----       \                     |       |
|       |                   |       |    \       \                    |       |
|       |_________________  |       |     \       \                   |       |
|                         | |       |      \       \                  |       |
|                         | |       |       \       \                 |       |
|                         | |       |        \       \                |       |
 -------------------------   ------- - - - - - -------  - - - - - - - | - - - |
                                                                      |       |
                                                                      /       /
                                                        --___________/       /
                                                       |                    /
                                                       |                   /
 _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ -250 --_____________---

```

The corners are rounded with a radius 25 points, the glyph width is 575 points.

I'll import the contributions in regular intervals, check the outlines, create bold and italic versions of them and update the upstream version. 

Contributions don't have to be release-ready. I'm happy to adjust curves, round the corners etc. If you need help, just ask. Fontdesign is fun, and I'm happy to help.



Again, if I react slowly, do not take it personally. I appreciate any help, suggestions and feedback, but sometimes I cannot react on the same day. 

</details>
