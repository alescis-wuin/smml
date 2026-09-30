# SMML Runtime

Runtime Spine / Carry Lab v0.5 contains:

- `Runtime.lua`: idempotent multi-entry bootstrap and diagnostics;
- `ContractRegistry.lua`: protected local contract registration/dispatch;
- `TransportService.lua`: request/reply transport over `SurvivalGame.network`;
- `StorageService.lua`: server-only `sm.storage` persistence probe;
- `CarryAdapter.lua`: empty `carry.resolveInsertTarget@1` adapter plus vanilla relay observation.

The runtime modules are loaded through temporary global factory handoffs. This deliberately relies only on the `dofile` execution side effect already proven by GP0.

v0.5.0 does **not** provide a custom Carry resolver yet. Its purpose is to prove that the final `CarryTool.cl_tryInsert` extension point is safe when empty and that a normal vanilla Resource Collector insertion still reaches `sv_n_sendItem` unchanged. `SMML.carry` remains a laboratory surface, not a stable public mod API.
