# Runtime Spine / custom Carry receiver lab v0.5.2

Purpose: validate one new Carry destination end-to-end while preserving the vanilla `CarryTool.sv_n_sendItem` relay.

Vanilla files modified:

- `Survival/Scripts/game/SurvivalPlayer.lua`: early idempotent bootstrap;
- `Survival/Scripts/game/SurvivalGame.lua`: lifecycle, transport and storage adapters;
- `Survival/Scripts/game/tools/CarryTool.lua`: resolver hook after all vanilla insert targets, vanilla-shaped RPC send for resolved targets, and observation at the existing `sv_n_sendItem` server relay;
- `Survival/Scripts/game/interactables/Chest.lua`: test-only `Chest.sv_e_receiveItem` receiver, injected only if that method is absent from the known vanilla baseline.

Installed runtime files:

- `Runtime.lua`;
- `ContractRegistry.lua`;
- `TransportService.lua`;
- `StorageService.lua`;
- `CarryAdapter.lua`;
- generated `RuntimeConfig.lua`.

## Carry receiver gate

v0.5.2 registers exactly one laboratory resolver: `probe.scrapChestReceiver@1`.

The physical fixture is the vanilla Scrap Chest (`7527cf2e-1705-4214-9d07-3dc374957e25`). It is intentionally not a vanilla Carry insertion target. With Scrap Wood in Carry, aiming directly at a Scrap Chest reaches the SMML resolver after all vanilla insertion branches have declined the target.

The resolver returns the hit Scrap Chest shape. `CarryTool.lua` then displays the normal Insert interaction and sends the existing `sv_n_sendItem` RPC. The unmodified server relay still dispatches `sv_e_receiveItem` to the target interactable. v0.5.2 temporarily supplies that receiver method on the `Chest` class.

The receiver is intentionally minimal: it derives the player's Carry container server-side, accepts exactly one Scrap Wood, spends it in a server container transaction, increments an in-memory receiver counter, and emits `carry.receiver.accept`. It does not put the item into the chest inventory. The chest is only the physical test endpoint.

This proves:

`unknown vanilla Carry target -> SMML resolver -> vanilla Carry RPC -> custom server receiver -> authoritative Carry mutation`.

## Safety

Installation is fail-closed on the known Scrap Mechanic 1.0.6 / engine 889 hashes for all four vanilla targets. Backups and restoration cover all four files. Only `Cache/Bundle/core_data.cbo` is invalidated.

The `Chest.lua` patch refuses to install if an existing `function Chest.sv_e_receiveItem` is detected, even when the file hash would otherwise be accepted.

The probe receiver:

- accepts only Scrap Wood (`968de65c-75f3-471b-954e-6165a4b6d3d6`);
- accepts only the vanilla Scrap Chest UUID;
- requires resolver provenance `probe.scrapChestReceiver@1`;
- requires `quantityA == 1`;
- ignores the client-supplied source container and derives `player:getCarry()` on the server;
- performs the spend in a server container transaction;
- persists no receiver state and adds no new RPC.

This is still a laboratory receiver, not a production authority boundary. A production receiver should additionally enforce world/distance/source policy appropriate to the gameplay contract.

## Test sequence

After installation on host and remote client:

1. start the host normally without `-dev` and load a Survival world;
2. place one vanilla Scrap Chest in an accessible location;
3. join with the remote client;
4. negative control: carry something other than Scrap Wood and aim at the Scrap Chest; the SMML Insert path must not activate;
5. positive case: carry one Scrap Wood and aim directly at the Scrap Chest;
6. trigger the primary Insert action once;
7. verify visually that the Scrap Wood disappears from Carry; it is intentionally not added to the chest inventory;
8. optionally repeat with another Scrap Wood to verify `receivedCount` increments;
9. close client and host cleanly, then collect artifacts.

Expected Carry fields after one positive insertion:

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
  "carry_receiver_accept_count": 1,
  "carry_receiver_reject_count": 0,
  "carry_receiver_received_max": 1,
  "carry_error_event_count": 0,
  "carry_server_passed": true,
  "carry_passed": true
}
```

Counts may exceed 1 if the positive interaction is repeated. The storage three-session gate does not need to be repeated for this Carry-only run.
