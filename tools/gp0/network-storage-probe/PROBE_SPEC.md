# GP0.5 Network / Storage Probe Specification — v0.2.0

## Objective

Close the remaining GP0 network/persistence uncertainty using a real host process and a real remote client process, while keeping the test reversible and independent from future public SMML API design.

## Topology

```text
Steam A / Scrap Mechanic A
  host + authoritative server
  separate Proton prefix
  host Save snapshot

Steam B / Scrap Mechanic B
  real remote client
  separate Steam home
  separate Proton prefix
```

The probe requires the same `runId` on both installations.

## Vanilla mutation

Only `SurvivalGame.lua` is patched. The patch adds:

- idempotent probe bootstrap;
- lifecycle instrumentation;
- one client->server RPC entry point;
- two server->client callbacks;
- hooks around `client_onClientDataUpdate`;
- fixed/update callbacks that advance small probe state machines.

Vanilla branches are not cancelled or replaced.

## Network contract envelope

```text
__smmlGp0Ns = true
runId
requestId
contractId
contractVersion
payload
```

The server validates run identity, descriptor and handler availability before dispatch.

Each handler is executed behind `xpcall` so the deliberate throwing handler can be tested without terminating the dispatcher.

## RPC matrix

| ID | Contract | Purpose |
|---|---|---|
| N-RPC-01 | `probe.ping@1` | baseline remote RPC + direct reply |
| N-RPC-02 | `probe.echo@1` | boolean serialization |
| N-RPC-03 | `probe.echo@1` | number serialization |
| N-RPC-04 | `probe.echo@1` | string serialization |
| N-RPC-05 | `probe.echo@1` | nested table serialization |
| N-RPC-06 | unknown | unknown-contract rejection |
| N-RPC-07 | `probe.ping@999` | unsupported version rejection |
| N-RPC-08 | `probe.ping@1` | invalid handler payload rejection |
| N-RPC-09 | `probe.throw@1` | deliberate handler exception |
| N-RPC-10 | `probe.ping@1` | dispatcher still works after N-RPC-09 |
| N-RPC-11 | nil envelope | serializer/callback fail-open behavior |

The first valid remote traffic also causes a server broadcast, proving `sendToClients` independently from direct replies.

## Client-data probe

Vanilla Survival uses channels 1 and 2. The probe therefore tests 3 and 4 under `pcall` rather than overwriting vanilla data.

Server phase:

```text
~1 second after server create:
  set channel 3 revision 1
  set channel 4 revision 1

first remote traffic:
  set accepted channels again as revision 2
```

The test run intentionally waits at least three seconds before B joins. A revision-1 callback on B therefore provides evidence that the engine retained and delivered client data to a later client.

A usable channel is one for which both are observed:

```text
clientdata.set.ok      on host
clientdata.receive.client on remote B
```

No assumption is made in advance that both 3 and 4 are valid.

## Storage model

The probe uses one unique server-only key:

```text
SMML_GP0_NS_V020_<runId>
```

The value contains explicit SMML logical namespaces:

```text
namespaces["com.smml.probe.a"].sharedKey = "A"
namespaces["com.smml.probe.b"].sharedKey = "B"
```

Both fake mods intentionally use the same logical data key concept while remaining distinct by `modId`.

### Session 1

```text
load -> absent
validate namespace structure
save schemaVersion=1
```

### Session 2

```text
load schemaVersion=1
validate namespaces
migrate 1 -> 2
save schemaVersion=2
```

### Session 3

```text
load schemaVersion=2
validate namespaces
no migration write required
```

Storage writes occur only at lifecycle transitions, never in the fixed-update loop after the phase completes.

## Lifecycle evidence

The host records:

- server create/unload/destroy;
- player join/left;
- whether a player is the host player;
- separate game-log source for every collected event.

The campaign requires one explicit B leave/rejoin while A stays online, plus three host launches of the same test world.

## Result correlation

Each installation produces its own result ZIP. `merge-results` rejects mismatched run IDs and evaluates both sides together.

A storage-restart pass requires schema events across at least three distinct game logs, not merely repeated callbacks in one process.

## Safety / recovery

- host Save is recursively copied and hashed before arming;
- post-probe Save is quarantined before the snapshot is restored;
- restored files are re-hashed;
- patched Lua is restored byte-for-byte;
- initial cache bytes/state are restored;
- result collection happens before restoration;
- all filesystem mutations require Scrap Mechanic to be stopped.

## Interpretation

A complete PASS provides evidence for a minimal GP1 design based on:

```text
SurvivalGame.network
  -> internal TransportService adapter

sm.storage
  -> SMML-owned logical namespace service
```

It does not freeze method names, manifest syntax, payload schema or storage backend as public API.
