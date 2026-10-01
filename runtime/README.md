# SMML Runtime

Runtime Spine / Custom Carry Receiver Lab v0.5.2 contains:

- `Runtime.lua`: idempotent multi-entry bootstrap and diagnostics;
- `ContractRegistry.lua`: protected local contract registration/dispatch;
- `TransportService.lua`: request/reply transport over `SurvivalGame.network`;
- `StorageService.lua`: server-only `sm.storage` persistence probe;
- `CarryAdapter.lua`: one Scrap Chest resolver plus a test-only authoritative receiver implementation.

The runtime modules are loaded through temporary global factory handoffs. This deliberately relies only on the `dofile` execution side effect already proven by GP0.

v0.5.2 registers `probe.scrapChestReceiver@1`. Scrap Wood aimed directly at a vanilla Scrap Chest is resolved as a new insertion destination after vanilla Carry targets have declined it. The CarryTool hook reuses the normal interaction prompt and `sv_n_sendItem` RPC. The server relay still invokes `sv_e_receiveItem`; v0.5.2 temporarily adds that method to `Chest.lua` and delegates its implementation to `SMML.carry.onCustomReceiverServer`.

The receiver derives the authoritative player Carry container on the server, spends one Scrap Wood in a transaction, and emits `carry.receiver.accept` with an in-memory `receivedCount`. It does not store the item in the chest. This is a laboratory proof, not a stable public mod API or final receiver security policy.
