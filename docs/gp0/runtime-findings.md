# SMML GP0.2 — Runtime findings from Carry / Storage Lab v0.1.4

## Result status

- Engine build observed: `1.0.6.889`.
- Two Survival world loads are present in the same game log.
- Storage matrix: `208/208` valid cases per world load; the two matrices are byte-logically identical: `true`.
- Successful reference run: second runtime / new-player world.
- Carry insertion: successful client -> RPC -> server -> ResourceContainer chain.

## Successful Carry chain

- seq 269: `carry.fixture.created` — targetUuid=a930a42f-63ed-4fb0-933e-56ce8a889cc5
- seq 270: `carry.fixture.ready` — targetUuid=a930a42f-63ed-4fb0-933e-56ce8a889cc5
- seq 271: `carry.loaded` — itemUuid=968de65c-75f3-471b-954e-6165a4b6d3d6
- seq 273: `carry.tryInsert.begin` — carryUuid=968de65c-75f3-471b-954e-6165a4b6d3d6
- seq 274: `carry.raycast` — success=true
- seq 275: `carry.target` — targetUuid=a930a42f-63ed-4fb0-933e-56ce8a889cc5
- seq 276: `carry.branch` — carryUuid=968de65c-75f3-471b-954e-6165a4b6d3d6, targetUuid=a930a42f-63ed-4fb0-933e-56ce8a889cc5, branch=container, canCollect=true
- seq 277: `carry.rpc.client` — carryUuid=968de65c-75f3-471b-954e-6165a4b6d3d6, targetUuid=a930a42f-63ed-4fb0-933e-56ce8a889cc5, rpc=sv_n_sendItem
- seq 278: `carry.rpc.server` — targetUuid=a930a42f-63ed-4fb0-933e-56ce8a889cc5, rpc=sv_n_sendItem, itemUuid=968de65c-75f3-471b-954e-6165a4b6d3d6
- seq 279: `carry.receive.server` — targetUuid=a930a42f-63ed-4fb0-933e-56ce8a889cc5, itemUuid=968de65c-75f3-471b-954e-6165a4b6d3d6
- seq 280: `carry.case` — targetUuid=a930a42f-63ed-4fb0-933e-56ce8a889cc5, itemUuid=968de65c-75f3-471b-954e-6165a4b6d3d6, success=true, carryQuantity=0, targetQuantity=1

## Storage acceptance matrix

| Container | Slots | Accepted test items |
|---|---:|---|
| Scrap Chest | 10 | Battery, Gasoline, Water, Potato, Fertilizer, Chemical, Potato Seed, Component Kit, Scrap Wood Block, Scrap Wheel, Connect Tool, Sledgehammer, Lift |
| Small Chest | 10 | Battery, Gasoline, Water, Potato, Fertilizer, Chemical, Potato Seed, Component Kit, Scrap Wood Block, Scrap Wheel, Connect Tool, Sledgehammer, Lift |
| Chest | 20 | Battery, Gasoline, Water, Potato, Fertilizer, Chemical, Potato Seed, Component Kit, Scrap Wood Block, Scrap Wheel, Connect Tool, Sledgehammer, Lift |
| Large Chest | 30 | Battery, Gasoline, Water, Potato, Fertilizer, Chemical, Potato Seed, Component Kit, Scrap Wood Block, Scrap Wheel, Connect Tool, Sledgehammer, Lift |
| XXL Chest | 100 | Battery, Gasoline, Water, Potato, Fertilizer, Chemical, Potato Seed, Component Kit, Scrap Wood Block, Scrap Wheel, Connect Tool, Sledgehammer, Lift |
| Locker | 4 | Battery, Gasoline, Water, Potato, Fertilizer, Chemical, Potato Seed, Component Kit, Scrap Wood Block, Scrap Wheel, Connect Tool, Sledgehammer, Lift |
| File Cabinet | 2 | Battery, Gasoline, Water, Potato, Fertilizer, Chemical, Potato Seed, Component Kit, Scrap Wood Block, Scrap Wheel, Connect Tool, Sledgehammer, Lift |
| Broken Microwave | 1 | Battery, Gasoline, Water, Potato, Fertilizer, Chemical, Potato Seed, Component Kit, Scrap Wood Block, Scrap Wheel, Connect Tool, Sledgehammer, Lift |
| Fridge | 20 | Potato |
| Gas Container | 5 | Gasoline |
| Water Container | 5 | Water |
| Battery Container | 5 | Battery |
| Potato Ammo Container | 5 | Potato |
| Fertilizer Container | 5 | Fertilizer |
| Seed Container | 5 | Potato, Potato Seed |
| Chemical Container | 5 | Chemical |

All 208 reference-run cases report `beginTransaction=true`, `dryRunCollected=1`, `abortIssued=true`, `unchangedAfterAbort=true`, no storage error, and no slot-count mismatch.

## Two-world aggregation issue

The collector currently aggregates every candidate log event since arming. Because the same log contains two Survival world loads, it reports `416` storage cases against `208` expected and therefore sets `storage_matrix_complete=false`. This is a collector bug, not a matrix failure. Results must be grouped by runtime/world session before completeness is evaluated.

## Tick error in first world

The first world emits 829 identical errors from `Lab.lua:433`: `Container does not exist`. They start after the Carry fixture was created and loaded. Later in that same session, `carryUuid` becomes the Resource Collector UUID itself, indicating the fixture was carried/moved and its original container handle became stale. The second world does not reproduce the error and completes the Carry test successfully.

Required hardening: validate container existence before every `totalQuantity`, stop the wait loop after target invalidation, and make the Carry fixture non-movable or recreate its container handle when necessary.

## Runtime/loadout observations

- `table: 0x25df2bf0`: newPlayer=true, inventorySize=40, freeSlots=38, tickErrors=0, carrySuccess=true.
- `table: 0x25e4e490`: newPlayer=false, inventorySize=40, freeSlots=28, tickErrors=829, carrySuccess=false.

The new-player run confirms an observed inventory size of `40` with `38` free slots at lab start.
