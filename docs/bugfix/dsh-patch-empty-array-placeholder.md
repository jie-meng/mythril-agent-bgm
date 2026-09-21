# dsh Patch Layer Broken by the `[]` Empty-Array Placeholder

## Problem Description

`dsh web` refused to start after BGM was set up:

```
Error: dsh: failed to parse overlay /Users/jiemeng/.dsh/profiles/web/cordis.patch.yml:
YAMLException: end of the stream or a document separator is expected (5:1)
4 | []
5 | - insert:
-----^
```

## Root Cause Analysis

dsh scaffolds every profile's `cordis.patch.yml` from a template whose last
line is a bare `[]` — the "empty patch list" placeholder:

```javascript
const PROFILE_PATCH_TEMPLATE = `# Your patch layer for this dsh profile, ...
# overrides, disables, and insert lists; \`!!js\` expressions allowed).
[]
`;
```

`DshIntegration._append_patch_entry_to_content()` was purely append-only: it
tacked the `- insert:` block onto the end of the file, leaving the `[]`
placeholder in place. A flow-sequence `[]` and a block-sequence entry cannot
coexist at the same level, so the file became unparsable. dsh parses patch
layers with a **fail-loud** policy (a present patch file that cannot apply is
a misconfiguration), so the profile aborted at boot instead of skipping BGM.

The mirror-image problem existed on cleanup: stripping our entry from a
scaffolded file leaves comment-only content, which parses as `null` and trips
a different dsh error — `must be a top-level YAML array`.

## Fix

Four changes in `src/mythril_agent_bgm/commands/integrations/dsh.py`:

1. `_EMPTY_PATCH_RE` matches a top-level `[]` line (column 0, so nested
   `config: []` values are never touched).
2. `_append_patch_entry_to_content()` strips the placeholder before appending.
3. `_restore_empty_placeholder()` re-adds it in `_strip_patch_entry()` when no
   top-level entry is left after cleanup (skipped when nothing remains — an
   absent patch file is dsh's "no user layer").
4. `_append_patch_entry()` now repairs an already-installed-but-broken file:
   the placeholder is dropped even when our entry is already present, so the
   next `bgm setup` heals an install broken by an older release.

Verified end to end against dsh's own parser (`yaml` resolved from the dsh
installation): scaffold + entry → parse error; after setup → `[{"insert":...}]`;
after cleanup → `[]`.

## Operational Notes

- The generated plugin JS (`index.js`) was never at fault and needs no change;
  only the patch-file writer was.
- `pyproject.toml` had `license = "MIT"`, which setuptools 75.6 rejects
  (`project.license` must be `{file}` or `{text}`). It is now
  `license = { text = "MIT" }`; without this, `pip install .` fails at
  metadata generation.
- A stale `build/` directory makes `pip install .` fail with
  `[Errno 17] File exists: build/bdist.../…dist-info`; `rm -rf build` first.
- The `bgm` CLI is installed non-editable in site-packages: `pip install .`
  is required after changing this code.
