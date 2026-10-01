# Runtime Spine / Carry resolver lab v0.5.1

Purpose: validate one real Carry target resolver while keeping the receiver fully vanilla.

Vanilla files modified:

- `Survival/Scripts/game/SurvivalPlayer.lua`: early idempotent bootstrap;
- `Survival/Scripts/game/SurvivalGame.lua`: lifecycle, transport and storage adapters;
- `Survival/Scripts/game/tools/CarryTool.lua`: idempotent bootstrap, resolver hook after all vanilla insert targets, vanilla-shaped RPC send for resolved targets, and observation at the existing `sv_n_sendItem` server relay.

Installed runtime files:

- `Runtime.lua`;
- `ContractRegistry.lua`;
- `TransportService.lua`;
- `StorageService.lua`;
- `CarryAdapter.lua`;
- generated `RuntimeConfig.lua`.

## Carry resolver gate

v0.5.1 registers exactly one laboratory resolver: `probe.resourceCollectorProxy@1`.

The test fixture uses only vanilla content. Build one creation containing:

- one vanilla Resource Collector;
- one ordinary block physically attached to that Resource Collector so both shapes belong to the same body.

With Scrap Wood in Carry, aim at the ordinary attached block instead of the Resource Collector itself. Vanilla `CarryTool.cl_tryInsert` does not recognize that block as an insertion target, so control reaches the SMML hook. The resolver scans the hit shape body, requires exactly one Resource Collector, and returns that Resource Collector shape as the resolved insertion target.

`CarryTool.lua` then performs the same interaction prompt and the same `sv_n_sendItem` RPC shape as vanilla, using the resolved Resource Collector as `targetShape`. The server keeps the original `sv_n_sendItem -> sv_e_receiveItem` path.

This deliberately proves target resolution without introducing a custom shapeset, custom receiver, Content Composer work, or a second server insertion mechanism.

## Safety

Installation is fail-closed on the known Scrap Mechanic 1.0.6 / engine 889 hashes for all three vanilla targets. Backups and restoration cover all three files. Only `Cache/Bundle/core_data.cbo` is invalidated.

The probe resolver:

- accepts only Scrap Wood (`968de65c-75f3-471b-954e-6165a4b6d3d6`);
- ignores a directly hit Resource Collector because that is already a vanilla target;
- requires exactly one Resource Collector on the proxy shape body;
- sends no custom RPC; the hook reuses `sv_n_sendItem`.

## Test sequence

After installation on host and remote client:

1. start the host normally without `-dev` and load a Survival world;
2. make sure a vanilla Resource Collector has at least one free slot;
3. attach one ordinary construction block directly to the Resource Collector so both shapes are part of the same creation/body;
4. join with the remote client;
5. on the remote client, carry one Scrap Wood;
6. aim at the attached ordinary block, not at the Resource Collector, and trigger the normal primary insert action once;
7. verify visually that the Scrap Wood leaves Carry and appears in the Resource Collector;
8. close client and host cleanly, then collect artifacts.

Expected Carry fields:

```json
// client
{
  "carry_resolver_register_count": 1,
  "carry_resolver_match_count": 1,
  "carry_resolver_client_rpc_count": 1,
  "carry_error_event_count": 0,
  "carry_client_passed": true,
  "carry_passed": true
}
```

```json
// host
{
  "carry_vanilla_server_relay_count": 1,
  "carry_resolver_server_rpc_count": 1,
  "carry_error_event_count": 0,
  "carry_server_passed": true,
  "carry_passed": true
}
```

Counts may exceed 1 if the interaction is repeated. The storage three-session gate does not need to be repeated for this Carry-only run.
