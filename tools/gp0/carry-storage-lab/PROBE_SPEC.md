# GP0.2 v0.1.4 probe specification

## Goals

The probe has four concrete goals:

1. validate multi-entry idempotent bootstrap with `SurvivalPlayer` occurring
   before `SurvivalGame` in the observed load order;
2. obtain the full runtime storage acceptance matrix for the selected 16
   containers x 13 items without manual dragging;
3. validate one deterministic CarryTool insertion end-to-end using
   Resource Collector + Scrap Wood;
4. preserve a recoverable, hashed pre-test Save state and exact vanilla game
   files/cache.

## Hook allocation

### SurvivalPlayer.lua

Top-level bootstrap only. It deliberately acts as the early hook entry point.
No gameplay callback is changed.

### SurvivalGame.lua

- top-level bootstrap;
- `server_onCreate`: registers the game instance with the lab;
- `server_onPlayerJoined`: registers the player;
- `server_onFixedUpdate`: advances a small lab state machine under `pcall`;
- adds one client RPC method that only displays GP0 chat instructions.

### CarryTool.lua

Top-level bootstrap plus instrumentation of `cl_tryInsert` and server insertion
RPCs. Vanilla branch decisions and RPC calls are not replaced or cancelled.

Detailed client logging is emitted only when the Create/Insert input state is
`start`, avoiding per-frame log spam.

### ResourceContainer.lua

Top-level bootstrap plus one entry marker in `sv_e_receiveItem`. Vanilla
transaction logic remains unchanged.

## Runtime orchestration stages

```text
disabled
  -> spawn_storage
  -> wait_storage
  -> storage_matrix
  -> loadout
  -> spawn_carry
  -> wait_carry_target
  -> load_carry
  -> wait_carry_insert
  -> complete | failed
```

The state exists only in the runtime global. The lab does not create a custom
persistent storage channel.

## Storage matrix semantics

Each fixture/item cell records:

- fixture id/title/UUID;
- expected and actual slot count;
- item id/title/UUID;
- `sm.container.canCollect(container, uuid, 1)`;
- whether `beginTransaction` succeeded;
- quantity reported by `sm.container.collect(..., false)`;
- `abortTransaction` issuance;
- item quantity before and after abort;
- container revision before and after.

The transaction is never committed. The test therefore exercises the engine
collection path while keeping the fixture contents unchanged.

Expected case count: `16 * 13 = 208`.

## Manual loadout

The automatic matrix does not depend on inventory capacity. After the matrix,
the probe best-effort adds one compact stack of each ordinary test item plus one
Connect Tool. Existing Sledgehammer/Lift are reused and are not duplicated.

Inventory size and free slots are measured at runtime; 40 slots is never
hard-coded.

## Carry case

Target:

```text
Resource Collector  a930a42f-63ed-4fb0-933e-56ce8a889cc5
```

Carried item:

```text
Scrap Wood  968de65c-75f3-471b-954e-6165a4b6d3d6
```

Success requires all final state evidence:

- ResourceContainer receive marker seen;
- player Carry has zero Scrap Wood;
- target Resource Collector contains at least one Scrap Wood.

The server RPC marker is separately recorded so a missing network hop can be
distinguished from a target-side failure.

## Fail-open rules

- runtime load is protected by `pcall(dofile, ...)`;
- lab tick is protected by `pcall` from `SurvivalGame.server_onFixedUpdate`;
- config/data/lab payloads are independently protected;
- the lab never cancels a vanilla CarryTool action;
- if a fixture cannot initialize, the matrix continues and emits a diagnostic
  row instead of blocking the world.

## Mutation/recovery rules

Before arming:

- Scrap Mechanic must be stopped;
- all owned game files must match installed hashes;
- the exact user-supplied `Save` directory is copied recursively;
- every copied file is SHA-256 hashed;
- snapshot verification must pass before `LabConfig.lua` is enabled.

After testing, `finish` restores the Save snapshot and vanilla Lua/cache with
hash verification. Post-lab Save/cache data are quarantined rather than deleted.
