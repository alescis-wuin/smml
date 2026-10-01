# SMML Runtime

Runtime Spine / Carry Resolver Lab v0.5.1 contains:

- `Runtime.lua`: idempotent multi-entry bootstrap and diagnostics;
- `ContractRegistry.lua`: protected local contract registration/dispatch;
- `TransportService.lua`: request/reply transport over `SurvivalGame.network`;
- `StorageService.lua`: server-only `sm.storage` persistence probe;
- `CarryAdapter.lua`: one real laboratory resolver plus vanilla relay observation.

The runtime modules are loaded through temporary global factory handoffs. This deliberately relies only on the `dofile` execution side effect already proven by GP0.

v0.5.1 registers `probe.resourceCollectorProxy@1`. When Scrap Wood is aimed at an ordinary shape that shares a body with exactly one vanilla Resource Collector, the resolver returns that Resource Collector as the insertion target. The CarryTool hook then reuses the normal interaction prompt and `sv_n_sendItem` RPC. The server still delegates to the vanilla receiver through `sv_e_receiveItem`.

This is intentionally a resolver-only proof. It adds no custom content and no custom receiver. `SMML.carry` remains a laboratory surface, not a stable public mod API.
