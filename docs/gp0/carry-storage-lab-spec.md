# SMML GP0.2 — Carry / Storage Laboratory specification

Target: Scrap Mechanic Survival 1.0.6 build 889
Basis: `smml-gp0-corpus-1.0.6.889.zip` + `SMML_GP0_STATIC_ANALYSIS_1.0.6.889.zip`

## 1. Critical separation: Storage vs CarryTool

The corpus shows two distinct mechanisms that must not be conflated.

### Storage path

Generic chests and storage furniture use an engine `chest.slots` definition, or a scripted container with filters. Examples: Scrap Chest, Chest, Large Chest, XXL Chest, Locker, File Cabinet, Broken Microwave, Fridge, Gas/Water/Battery/etc. containers.

These are **not** entries in `CarryTool.ContainerInsertTargets`, `GenericInsertTargets`, or `HarvestableInsertTargets`.

### CarryTool insertion path

`Survival/Scripts/game/tools/CarryTool.lua` only recognizes:

- Refinebot
- Resource Collector
- Ore Collector
- Crushbot
- Plasma Drill levels 1–3
- Gyro Core Slot
- Power Activator harvestable

Therefore GP0.2 needs two result matrices:

1. `storage-matrix.csv` — container/filter/tool-storage behavior.
2. `carry-matrix.csv` — CarryTool client/server insertion path.

## 2. New-player inventory facts

`SurvivalGame.server_onPlayerJoined` gives a non-dev new player:

- slot 0: Sledgehammer (`bb641a4f-e391-441c-bc6d-0ae21a069476`)
- slot 1: Lift (`8f190ce2-3a59-423e-8483-a7aa67bd5bc0`)

The total player inventory size is not hard-coded in the Survival Lua corpus. The probe must query `player:getInventory():getSize()` at runtime and must not assume 40 slots.

The vanilla `/starterkit` implementation in `BaseWorld.lua` demonstrates that a Connect Tool can be collected into a normal Chest container with `sm.container.collect`.

## 3. Storage fixtures

### Generic / engine chest fixtures

| ID | Title | UUID | Slots | Notes |
|---|---|---|---:|---|
| scrap_chest | Scrap Chest | `7527cf2e-1705-4214-9d07-3dc374957e25` | 10 | no pipe |
| small_chest | Small Chest | `4c474cff-3f6a-4306-93d1-c4c74578afd2` | 10 | pipe-capable |
| chest | Chest | `fcfae5e2-1df9-47d8-bb9a-30bec9b5b1f5` | 20 | generic |
| large_chest | Large Chest | `ad35f7e6-af8f-40fa-aef4-77d827ac8a8a` | 30 | pipe-capable |
| xxl_chest | XXL Chest | `9601f2ca-9552-48b0-afc1-b0f200461114` | 100 | multi-pipe |
| locker | Locker | `d0afb527-e786-4a22-a907-6da7e7cba8cb` | 4 | generic chest storage |
| file_cabinet | File Cabinet | `90dbaebf-8ea1-4a5a-8f6f-86ddde77c6c8` | 2 | generic chest storage |
| broken_microwave | Broken Microwave | `d4e6c84c-a493-44b1-81aa-4f4741ea3ed8` | 1 | spaceship storage |

### Scripted / filtered fixtures

| ID | Title | UUID | Slots | Rule |
|---|---|---|---:|---|
| fridge | Fridge | `f08d772f-9851-400f-a014-d847900458a7` | 20 | `FoodContainer`; explicit food UUID allow-list |
| gas_container | Gas Container | `056e5ff1-f030-40df-946a-b830bf494c92` | 5 | only Gasoline; per-slot cap 20 |
| water_container | Water Container | `ea10d1af-b97a-46fb-8895-dfd1becb53bb` | 5 | only Water; per-slot cap 20 |
| battery_container | Battery Container | `da4833fd-f981-4e08-a9f7-48e630a7c146` | 5 | only Battery; per-slot cap 20 |
| ammo_container | Potato Ammo Container | `096d4daf-639e-4947-a1a6-1890eaa94464` | 5 | only Potato; per-slot cap 100 |
| fertilizer_container | Fertilizer Container | `76331bbf-abbd-4b8d-bb54-f721a5b6193b` | 5 | only Fertilizer; per-slot cap 20 |
| seed_container | Seed Container | `38ec258d-c644-4f08-8635-3f7434c884dd` | 5 | `sm.item.getPlantableUuids()`; per-slot cap 20 |
| chemical_container | Chemical Container | `be29592a-ef58-4b1d-b18c-895023abd27f` | 5 | only Chemical; per-slot cap 20 |

Note: Chemical Container occurs in two baseline shape sets with the same UUID and different `physicsMaterial`; this is an existing baseline duplicate and must not be treated as a mod collision during this probe.

## 4. Storage test items

| ID | Title | UUID | Static stack size | Purpose |
|---|---|---|---:|---|
| battery | Battery | `910a7f2c-52b0-46eb-8873-ad13255539af` | 20 | Battery Container positive |
| gasoline | Gasoline | `d4d68946-aa03-4b8f-b1af-96b81ad4e305` | 20 | Gas Container positive |
| water | Water | `869d4736-289a-4952-96cd-8a40117a2d28` | 20 | Water Container positive |
| potato | Potato | `bfcfac34-db0f-42d6-bd0c-74a7a5c95e82` | 100 | Ammo + Fridge; also has `plantable` metadata |
| fertilizer | Fertilizer | `ac0b5b0a-14e1-4b31-8944-0a351fbfcc67` | 20 | Fertilizer Container positive |
| chemical | Chemical | `f74c2891-79a9-45e0-982e-4896651c2e25` | 20 | Chemical Container positive |
| potato_seed | Potato Seed | `eb1ef696-5c05-4662-9e47-fe1e0875ff84` | 20 | Seed Container positive; has `plantable` metadata |
| component_kit | Component Kit | `5530e6a0-4748-4926-b134-50ca9ecb9dcf` | 20 | generic consumable negative control for filtered containers |
| scrap_wood_block | Scrap Wood Block | `1fc74a28-addb-451a-878d-c3c605d63811` | 500 | material / block control |
| scrap_wheel | Scrap Wheel | `59f6951a-a450-42bf-ad03-54567cb70245` | 5 | ordinary placeable part control |
| connect_tool | Connect Tool | `8c7efc37-cd7c-4262-976e-39585f8527bf` | runtime | positive tool control; vanilla `/starterkit` puts it in a Chest |
| sledgehammer | Sledgehammer | `bb641a4f-e391-441c-bc6d-0ae21a069476` | runtime | special starter tool control |
| lift | Lift | `8f190ce2-3a59-423e-8483-a7aa67bd5bc0` | runtime | special starter tool control |

The probe should query actual tool/container collection behavior at runtime rather than invent a stack size for tools.

## 5. Static expected storage behavior

The expected result is derived from the container filters, not from assumptions about GUI behavior.

- Generic chest fixtures: no UUID filter is declared. Destination acceptance should be probed for every test item. Connect Tool has a vanilla positive-control precedent in `BaseWorld.lua`.
- Fridge: among the selected items, Potato is explicitly in `FoodUuids`; the other selected items are not.
- Gas Container: Gasoline only.
- Water Container: Water only.
- Battery Container: Battery only.
- Potato Ammo Container: Potato only.
- Fertilizer Container: Fertilizer only.
- Chemical Container: Chemical only.
- Seed Container: runtime query required for the exact set returned by `sm.item.getPlantableUuids()`. Both Potato and Potato Seed carry `plantable` metadata in the Survival data and are expected candidates, but the runtime result is authoritative.

## 6. Recommended automated storage test

Do not require the player to drag 13 items through 16 containers manually.

For every freshly created fixture container and every test item, run on the server:

1. locate container 0 after the interactable has completed creation;
2. record `sm.container.canCollect(container, uuid, 1)`;
3. if true, start a transaction;
4. collect exactly one unit into the empty fixture;
5. commit and record success/failure;
6. immediately spend the same unit back out in a second transaction;
7. verify the container returned to its initial empty state;
8. log revision and failure reason when available.

For the three tools, additionally distinguish:

- destination `canCollect` behavior;
- direct server transaction behavior;
- manual GUI behavior (small human spot-check), because GUI-level restrictions may differ from raw container capability.

This produces `storage-matrix.csv` automatically. Manual testing is reduced to a few selected cells.

## 7. Inventory loadout

Keep the requested visual/manual loadout, but make it secondary to the automated matrix.

Before injecting anything:

- query `inventory:getSize()`;
- enumerate occupied slots;
- preserve the existing Sledgehammer and Lift;
- calculate free slots;
- refuse or reduce the optional manual loadout if it does not fit atomically.

Recommended manual loadout:

- one of each of the 16 storage fixtures, when `sm.container.canCollect(playerInventory, fixtureUuid, 1)` permits it;
- one stack of each non-tool test item;
- Connect Tool x1;
- reuse the existing Sledgehammer and Lift.

Suggested quantities for non-tool test items: 16 where the natural stack allows it; Scrap Wheel max 5. Quantities are convenience only; the automated matrix consumes nothing permanently.

If a fixture cannot be collected into player inventory, spawn it as a lab fixture and record `fixtureMode=spawn` rather than failing the experiment.

## 8. CarryTool target matrix from vanilla code

### ContainerInsertTargets

| Target | UUID | Container slot | Accepted carry items |
|---|---|---:|---|
| Refinebot | `5cb15c93-4fa9-48da-9974-2e95ca6c9e1c` | 1 | Scrap Wood, Wood, Scrap Metal, Metal, Scrap Stone; code also references `ITEMS.obj_harvest_crystal` |
| Resource Collector | `a930a42f-63ed-4fb0-933e-56ce8a889cc5` | 0 | same resource-harvest group |
| Ore Collector | `80680f7d-5f8a-4bf7-962b-ebd07481cd0a` | 0 | eight ore-casing UUIDs |
| Crushbot | `b593a935-802a-4715-b27f-739a091a8977` | 1 | same eight ore-casing UUIDs |

Resource-harvest UUIDs confirmed in current data:

- Scrap Wood `968de65c-75f3-471b-954e-6165a4b6d3d6`
- Wood `f99ebc34-4821-4b39-a625-b839c5802ed5`
- Scrap Metal `5cb39ea5-554d-4c40-9d9a-6b2dd59de953`
- Metal `7468db55-b29d-4ce0-82b9-2414f493a376`
- Scrap Stone `02ee2a98-bd8d-4a09-bb69-38edaf66b8e1`

The current generated `survival_items.lua` does **not** define `ITEMS.obj_harvest_crystal`, although `survival_collections.lua` and `ResourceContainer.lua` reference it. Do not build a fixture around that symbol; record it as a baseline inconsistency.

Ore-casing group:

- `47e140e8-eec1-4066-ad75-57557ea07e9b` Goopite Ore
- `32111055-2a23-413b-a490-da619b85a9bf` Crimsonite Ore
- `7aab1deb-40a1-4af1-a245-71c6c8439d2f` Thornite Ore
- `4f33ee9c-397a-4f47-b91c-32ae96cbe507` Rich Ore
- `4edfeea0-4dd9-4260-82b0-a812b4179296` Mixed Ore
- `ef4cc633-3cd1-4e13-9502-b498c4a4c7af` Mixed Ore
- `4d3d1a02-83ff-4795-9fa7-85eaee8f36f2` Mixed Ore
- `05a3e48b-0483-4897-b1e3-370271f815ed` Mixed Ore

### GenericInsertTargets

- Gyro Core Slot `a5093336-af02-42c4-8afd-196f22a0917f` accepts Gyro Core `5f5b2a0d-b629-4bea-93ca-e1f45ccac62b`.
- Plasma Drill L1 `9b9c0a82-a9bf-41d4-a599-58182f162058` accepts the four mixed ore casings.
- Plasma Drill L2 `660c50e1-081d-449c-a405-785d4c26328d` accepts the four mixed ore casings.
- Plasma Drill L3 `4a3d40d4-ce86-4a68-b042-8d107ea39d78` accepts the four mixed ore casings.

### HarvestableInsertTargets

- Power Activator harvestable `895f5d04-c29a-46fd-bff5-742fc310940b` accepts Power Station Battery `b5ce8bc0-e8b3-418f-9267-81b85a8eba0d` through `sv_n_sendItemToHarvestable`.

## 9. Minimal deterministic CarryTool runtime case

The cheapest reliable case is:

- target: Resource Collector `a930a42f-63ed-4fb0-933e-56ce8a889cc5`;
- carried item: Scrap Wood `968de65c-75f3-471b-954e-6165a4b6d3d6`.

Reasons:

- both are explicitly paired by `ContainerInsertTargets`;
- Resource Collector implements `sv_e_receiveItem` and validates the same accepted-item group;
- Scrap Wood is a real `carryItem=true`, `showInInventory=false` shape already observed in the previous runtime run;
- no dungeon progression is required if the probe creates the Resource Collector fixture itself;
- vanilla code demonstrates server-side population of player carry containers with `sm.container.setItem` in `LostCarry.lua`.

Expected chain:

`cl_tryInsert(start)` → `sv_n_sendItem` → `ResourceContainer.sv_e_receiveItem` → spend carry slot 0 → collect target slot.

For this one case the player action can be reduced to: aim at the pre-positioned Resource Collector and press Insert once.

## 10. Fixture creation and mutation policy

Use only runtime APIs already observed in vanilla code:

- `sm.shape.createPart(...)` for part fixtures;
- `sm.container.collect(...)`, `setItem(...)`, `spend(...)` inside transactions;
- `player:getInventory()` and `player:getCarry()`.

Do not edit save DB/files directly.

Before any world/inventory mutation:

1. recursively snapshot the Save tree outside the game directory;
2. hash the snapshot manifest;
3. record the target save and game build;
4. only then enable lab mutation.

After the run, provide both:

- best-effort runtime cleanup of fixtures;
- authoritative post-game restore from the pre-run save snapshot when requested.

## 11. Telemetry required for v0.1.4

### Storage events

- `storage.fixture.created`
- `storage.fixture.ready`
- `storage.case.begin`
- `storage.case.canCollect`
- `storage.case.collectCommit`
- `storage.case.rollbackCommit`
- `storage.case.end`
- `storage.fixture.cleanup`

Each case must include fixture ID/title/UUID, container size, item ID/title/UUID, and transaction result.

### Carry events

- current `carry.tryInsert.begin`
- raycast result type
- target UUID/title/class
- selected branch (`container`, `generic`, `harvestable`, `none`)
- accepted-list membership
- target-container availability and `canCollect`
- `carry.rpc.send`
- `carry.rpc.server`
- `carry.receive.server`
- transaction commit/failure

## 12. Proposed v0.1.4 pass criteria

Storage Lab passes when:

- all 16 fixture types are either instantiated or explicitly reported unsupported;
- the complete automated item × container matrix is exported;
- every successful probe transaction is rolled back and verified empty;
- Connect Tool generic-chest positive control is reproduced;
- Sledgehammer/Lift raw-container and manual-GUI behavior are distinguished;
- no test depends on farming or crafting.

Carry Lab passes when:

- Resource Collector + Scrap Wood reaches `sv_n_sendItem`;
- `ResourceContainer.sv_e_receiveItem` is observed;
- server transaction success is observed;
- the carry container becomes empty or changes exactly as vanilla expects.

