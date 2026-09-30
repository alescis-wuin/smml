# GP0.2 Runtime Probe — Specification

Version: `0.1.3`

## Questions addressed

- **P-HOOK-001** — Is one probe global visible from `SurvivalGame`, `SurvivalPlayer`, `CarryTool`, an existing `ScriptableObjectClass` (`QuestManager`) and an existing `ShapeClass` (`Crafter`)?
- **P-HOOK-002** — What is the observed file-evaluation and lifecycle callback order?
- **P-HOOK-003** — Can the runtime file/bootstrap be evaluated repeatedly without re-initializing state?
- **P-HOOK-004** — Do `xpcall` and `debug.traceback` isolate one failed handler while a later handler continues?
- **P-HOOK-005 (preliminary)** — How often does the candidate `CarryTool.cl_tryInsert` path get entered? This version only counts/limits logs; it is not a performance benchmark yet.
- **P-HOOK-006 (preliminary)** — Observe client drop and server `sv_n_dropCarry` paths without cancellation. Active cancellation is intentionally deferred.

## Patched vanilla files

- `Survival/Scripts/game/SurvivalGame.lua`
- `Survival/Scripts/game/SurvivalPlayer.lua`
- `Survival/Scripts/game/tools/CarryTool.lua`
- `Survival/Scripts/game/managers/QuestManager.lua`
- `Survival/Scripts/game/interactables/Crafter.lua`

All five must match the known clean `1.0.6.889` SHA-256 values before installation.

## Added file

- `Survival/Scripts/SMMLProbe/Runtime.lua`

## Cache operation

`Cache/Bundle/core_data.cbo` is copied to the external probe state directory and removed before first probe launch. The first launch must therefore be a normal launch without `-dev`. On uninstall, any probe-era rebuilt cache is quarantined and the exact pre-probe cache is restored.

## Behavior policy

The probe is passive:

- no carry operation is cancelled;
- no inventory transaction is changed;
- no save database is edited directly;
- no extra shapes or recipes are registered;
- diagnostics are written only through normal game logging.
