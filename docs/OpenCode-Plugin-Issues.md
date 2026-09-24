# OpenCode Plugin Issues and Fixes

## Problem Description

The AI BGM plugin for OpenCode would stop playing music after some time during a session. Restarting OpenCode would temporarily fix the issue, but the problem would recur.

## Root Cause Analysis

After investigation, the issue is primarily caused by **bugs in OpenCode's plugin system**, not our plugin code.

### 1. Fire-and-Forget Event Handlers

**Issue**: [#16879](https://github.com/anomalyco/opencode/issues/16879)

OpenCode's plugin event handlers are called without awaiting their promises. In `plugin/index.ts` line 138:

```typescript
hook["event"]?.({ event: input as any })  // Not awaited
```

This means async operations like `await $\`bgm play work 0\`` may not complete before the next event is processed.

**Status**: Closed (fixed)

### 2. session.created Event Not Firing

**Issue**: [#14808](https://github.com/anomalyco/opencode/issues/14808)

The `session.created` event sometimes doesn't fire, causing `currentSessionID` to remain `null`. This breaks the session ID check in subsequent `message.updated` events:

```javascript
props?.info?.sessionID === currentSessionID  // Always false when currentSessionID is null
```

**Status**: Open

### 3. Race Condition on Session Idle

**Issue**: [#15267](https://github.com/anomalyco/opencode/issues/15267)

A race condition exists between `session.idle` event handling and session teardown, which can cause events to be processed incorrectly.

**Status**: Open

### 4. Plugin System Robustness

**Issue**: [#18279](https://github.com/anomalyco/opencode/issues/18279)

Multiple robustness gaps in the plugin system, including:
- Plugin config hook errors crash entire bootstrap
- Insufficient error isolation between hooks
- Async errors in `prompt_async` silently dropped

**Status**: Closed

## Our Fix

Modified `opencode.py` to make the plugin more resilient to OpenCode's known issues:

### Changes Made

1. **Removed session ID check**: Since `session.created` may not fire, we no longer check `currentSessionID` in `message.updated` handler.

2. **Fire-and-forget command execution**: Added a helper function that catches and ignores errors:

```javascript
const runBgm = (cmd) => {
  $`bgm ${cmd}`.quiet().nothrow().catch(() => {});
};
```

3. **Simplified state management**: Removed redundant session ID checks in `session.idle` and `session.deleted` handlers.

### Before

```javascript
case "message.updated":
  if (
    !isWorking &&
    props?.info?.role === "user" &&
    props?.info?.sessionID === currentSessionID &&  // May fail if session.created didn't fire
    Date.now() - lastIdleTime > DEBOUNCE_MS
  ) {
    isWorking = true;
    await $`bgm play work 0`.quiet().nothrow();  // May not complete
  }
  break;
```

### After

```javascript
case "message.updated":
  if (
    !isWorking &&
    props?.info?.role === "user" &&
    Date.now() - lastIdleTime > DEBOUNCE_MS
  ) {
    isWorking = true;
    runBgm("play work 0");  // Fire-and-forget with error handling
  }
  break;
```

## Testing

After applying the fix:

1. Run `bgm setup` to regenerate the plugin
2. Restart OpenCode
3. The BGM should now play reliably across multiple prompts

---

## Issue: Done Music Plays on Subagent Completion (2026-06-03)

### Problem

When OpenCode uses subagents (e.g. via the `task` tool), each subagent creates its own session. When a subagent finishes, it triggers a `session.idle` event, which caused the "done" music to play prematurely — even though the main agent was still working.

### Root Cause

The original plugin had no concept of session hierarchy. All `session.idle` events were treated equally, so any subagent going idle would trigger the done sound.

Additionally, two bugs were found during the fix:

1. **Wrong field name for `session.idle`**: The SDK defines `EventSessionIdle` as `{ type: "session.idle"; properties: { sessionID: string } }`. The fix incorrectly used `props?.info?.id` instead of `props?.sessionID`, which would have made done music never play.

2. **`is_configured()` only checked file existence**: After upgrading the plugin code, `bgm setup` would report "No changes to apply" because the old plugin file still existed. Fixed by comparing file content against the generated output.

### SDK Event Structures (verified from `@opencode-ai/sdk`)

| Event | Session ID field |
|-------|-----------------|
| `session.created` | `properties.info.id` (via `Session` object) |
| `session.idle` | `properties.sessionID` (direct string) |
| `session.deleted` | `properties.info.id` (via `Session` object) |

The `Session` type also has a `parentID` field: subagent sessions have it set; top-level sessions do not. This is used to distinguish main sessions from subagent sessions.

### Fix

- Track `mainSessionID` from the first `session.created` event without a `parentID`
- On `session.idle`, compare `props?.sessionID === mainSessionID` before playing done
- On `session.deleted`, only stop and reset when the main session is deleted
- `is_configured()` now compares plugin file content against `_generate_plugin()` output

### Commits

| Commit | Description |
|--------|-------------|
| `f3f7a29` | fix: only play done music on main agent idle, not subagents |
| `3a79543` | fix: regenerate opencode plugin when content is outdated |
| `0aaa6a6` | fix: correct session ID field names and use parentID for subagent detection |

---

## Issue: Plugin Rejected by OpenCode 2.x (V2 Plugin API) (2026-09-24)

### Problem

OpenCode 2.0.15 refused to load the generated plugin and showed, at startup:

```text
Server plugin error
Plugin: ~/.config/opencode/plugins/opencode-bgm.js
Status: failed        Runtime: server
Error: Plugin must export a default definition with an id and an effect or setup function.
```

`bgm setup` had written the plugin successfully — the file existed and was valid
JavaScript. The failure was entirely on OpenCode's side.

### Root Cause

OpenCode 2.x replaced the V1 plugin API. The module schema is now a struct, and
the loader decodes the **module namespace**, not a callable:

```ts
// packages/core/src/plugin/module.ts @ v2.0.15
const Module = Schema.Struct({
  default: Schema.Union([
    Schema.Struct({ id: Schema.String, effect: /* function */ }),
    Schema.Struct({ id: Schema.String, setup: /* function */ }),
  ]),
})
```

Our generated file default-exported a function (the V1 contract), so decoding
failed on the `default` key. The server log carries the real cause, which the TUI
hides behind its summary line:

```text
message="failed to load plugin" target=.../opencode-bgm.js ref=err_4baddd2c
cause="Cause([Fail(PluginModule.LoadError: Plugin must export a default definition
 with an id and an effect or setup function.
 (cause: SchemaError(Expected object\n  at [\"default\"])))])"
```

`SchemaError(Expected object at ["default"])` — that is the whole story: a function
is not an object. Always read `cause=` in `~/.local/share/opencode/log/opencode.log`,
keyed by the `ref=err_...` shown in the TUI.

### Two Traps Beyond the Export Shape

**1. `event.properties` no longer exists.** V2 events are flat
(`{ id, created, type, location?, durable?, data }`), so V1 handlers reading
`event.properties.info.role` now see `undefined` — a silent no-op, not an error.
`message.updated` is gone as well; the work/done anchors became
`session.inbox.enqueued`, `session.execution.started` and
`session.execution.succeeded` / `.failed` / `.interrupted`.

**2. One plugin instance per open location, receiving every event.** Verified with
a probe plugin while 7 directories were open in the shared `opencode serve
--service` daemon: a single `session.execution.started` reached all 7 instances
(the daemon holds one multiplexed `/api/event` SSE fan-out). Filtering only on
`data.location.directory` was **not** enough, because the location is a property of
the *event*; `session.inbox.enqueued`, `session.execution.*` and `session.status`
do not repeat it inside `data` (`session.execution.started` has `location:
undefined` entirely). Every instance therefore adopted the same session and each
one restarted the music: 6–7 `bgm play work 0` calls per run.

The working gate is: drop events whose own `location.directory` differs from
`ctx.location.directory`, adopt exactly one main session per instance (subagents are
skipped via `data.parentID`), and afterwards key everything on that `sessionID`.
After the fix: exactly one `play work 0` and one `play done` per run.

### Migration Map (V1 → V2)

| V1 | V2 |
|----|----|
| `export default async () => ({ ...hooks })` | `export default { id, setup(ctx) { ...; return cleanup } }` |
| returned hooks object | imperative `ctx.<domain>.hook(...)` / `ctx.<domain>.transform(...)` registrations |
| `event: async ({ event })` hook | `for await (const event of ctx.event.subscribe({ signal }))` |
| `event.properties` | `event.data` |
| `message.updated` (`role === "user"`) | `session.inbox.enqueued` (`data.item.type === "user"`) |
| `session.idle` / `session.status` | still present, plus `session.execution.{started,succeeded,failed,interrupted}` |
| `tool.execute.before` (`tool === "question"`) | no tool-name field in `session.tool.*`; use `form.created` / `permission.asked` |
| `session.created` → `properties.info.id` | `data.sessionID` (+ `data.parentID`, `data.location.directory`) |

### Fix

`_generate_plugin()` now renders `_PLUGIN_TEMPLATE` (an OpenCode 2.x `{ id, setup }`
module) instead of the V1 function, and the path is injected with `json.dumps()` so
Windows separators survive as a valid JS string literal. Subscriptions reconnect if
the SSE stream ends, and `setup` returns an abort-based cleanup.

### Not Changed

- `mimo.py` still emits the V1 shape. MiMo Code is an OpenCode fork and only shares
  the plugin system up to the version it forked; it is not installed here, so its
  contract is unverified. Do not port this blindly — check `mimo`'s plugin loader first.
- OpenCode 1.x users: the V2 shape is what 2.x wants; if a 1.x load error ever
  appears, that is the trade-off to revisit.

### Verification

| Step | Result |
|------|--------|
| `node --check` on generated plugin (Unix + Windows path) | pass |
| Daemon log after reload | no `failed to load plugin` for `opencode-bgm.js` |
| `opencode run` in a fresh directory, `bgm` stubbed by a logging wrapper | `1 play work 0`, `1 play done` |
| Same run before the location fix | 7 `play work 0` + 7 `play done` |
| `pytest tests/` | 113 passed |
| `black --check`, `mypy` on the changed file | clean |
| Installed-package drift | site-packages copy synced from the repo (0.1.11 vs 0.1.12) so `bgm setup` cannot write the V1 file back; `is_up_to_date()` → `True` |

---

## Related OpenCode Issues

| Issue | Title | Status |
|-------|-------|--------|
| [#16879](https://github.com/anomalyco/opencode/issues/16879) | await plugin event handlers on session.idle | Closed |
| [#14808](https://github.com/anomalyco/opencode/issues/14808) | Plugin event listener for "session.created" not firing | Open |
| [#15267](https://github.com/anomalyco/opencode/issues/15267) | opencode run teardown race after session.idle | Open |
| [#18279](https://github.com/anomalyco/opencode/issues/18279) | Plugin system robustness gaps | Closed |
