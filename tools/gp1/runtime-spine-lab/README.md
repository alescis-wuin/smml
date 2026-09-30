# Runtime Spine / Carry lab v0.5.0

Purpose: validate the first gameplay hook boundary without introducing custom content yet.

Vanilla files modified:

- `Survival/Scripts/game/SurvivalPlayer.lua`: early idempotent bootstrap;
- `Survival/Scripts/game/SurvivalGame.lua`: lifecycle, transport and storage adapters;
- `Survival/Scripts/game/tools/CarryTool.lua`: idempotent bootstrap, one empty resolver hook after all vanilla insert targets and an observation at the existing `sv_n_sendItem` server relay.

Installed runtime files:

- `Runtime.lua`;
- `ContractRegistry.lua`;
- `TransportService.lua`;
- `StorageService.lua`;
- `CarryAdapter.lua`;
- generated `RuntimeConfig.lua`.

## Carry gate

v0.5.0 intentionally has zero resolvers. The client hook returns to vanilla `false` after recording an interaction-start event. It sends no extra RPC.

A successful run proves two independent facts:

1. on the remote client, an insertion attempt against a non-vanilla target reaches the empty SMML hook (`carry.resolve.empty`);
2. an ordinary Scrap Wood insertion into a vanilla Resource Collector still reaches the original server relay (`carry.vanilla.rpc.server`).

This is a non-regression probe before adding a custom receiver.

## Safety

Installation is fail-closed on the known Scrap Mechanic 1.0.6 / engine 889 hashes for all three vanilla targets. Backups and restoration cover all three files. Only `Cache/Bundle/core_data.cbo` is invalidated.

## Test sequence

After installation on host and remote client:

1. start the host normally without `-dev` and load a Survival world;
2. join with the remote client;
3. on the remote client, carry Scrap Wood and aim at a body/target that is not a vanilla insertion target; press the normal primary insert action once;
4. still on the remote client, carry Scrap Wood to a vanilla Resource Collector with free capacity and insert one unit normally; verify the item is actually received;
5. close client and host cleanly, then collect artifacts.

Expected Carry fields:

```json
// client
{
  "carry_empty_resolve_count": 1,
  "carry_client_passed": true,
  "carry_error_event_count": 0,
  "carry_passed": true
}
```

```json
// host
{
  "carry_vanilla_server_relay_count": 1,
  "carry_server_passed": true,
  "carry_error_event_count": 0,
  "carry_passed": true
}
```

Counts may exceed 1 if the interaction is repeated. Previous Runtime Spine gates remain evidence from v0.1-v0.4; the storage three-session gate is not required to be repeated for this Carry-only run.
