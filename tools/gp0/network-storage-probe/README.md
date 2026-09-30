# SMML GP0.5 Network / Storage Probe v0.2.0

Target: Scrap Mechanic Survival 1.0.6, engine build 889, Steam public build 25442087.

This package is a disposable research probe for the remaining GP0.5 questions:

- real remote-client RPC across two Scrap Mechanic processes;
- server -> client and server -> clients traffic;
- contract/version/payload rejection and handler-failure isolation;
- `Game.network:setClientData` behavior on channels not used by vanilla Survival;
- remote disconnect/reconnect and repeated world/process lifecycle;
- `sm.storage` persistence across restarts;
- explicit SMML logical namespaces and a schema 1 -> 2 migration.

It is **not** the future public SMML runtime API.

## Mutation surface

Only one vanilla Lua file is patched, and only if its SHA-256 exactly matches the known clean 1.0.6.889 baseline:

```text
Survival/Scripts/game/SurvivalGame.lua
SHA-256 934beb15dff2f34638128a56aa1be8586e363bc1a5d564698e9b8f09bf9d35c4
```

Temporary files are installed under:

```text
Survival/Scripts/SMMLProbeNS/Runtime.lua
Survival/Scripts/SMMLProbeNS/Probe.lua
Survival/Scripts/SMMLProbeNS/ProbeConfig.lua
```

`Cache/Bundle/core_data.cbo` is backed up when present, then invalidated. The exact pre-probe cache state is restored at uninstall.

## Safety model

- `install` is passive; no network/storage test executes while the config is disabled.
- The host role cannot be armed without a recursive, hashed snapshot of the exact `User_*/Save` directory.
- The client role does not mutate a world Save and therefore takes no Save snapshot.
- `sm.storage` is written only during server/world creation phases, never every tick.
- The probe uses a run-specific storage key and restores the host Save after the campaign.
- Network callbacks and probe hooks are wrapped so test failures should fail open rather than cancel vanilla behavior.
- Symlinked game target / Save roots are refused by the harness.
- The harness refuses to operate while any Scrap Mechanic process is running.

## Before installing

Both Scrap Mechanic instances must be closed.

If the older Carry/Storage lab is still installed in either game copy, restore it first. This probe intentionally refuses a modified `SurvivalGame.lua`.

For the current two-installation setup:

```bash
HOST_GAME="$HOME/.local/share/Steam/steamapps/common/Scrap Mechanic"
CLIENT_GAME="$HOME/smml-multiplayer-client/.local/share/Steam/steamapps/common/Scrap Mechanic"

HOST_STATE="/developpement/seynax/smml/smml-gp0-network-storage-host-v0.2.0"
CLIENT_STATE="/developpement/seynax/smml/smml-gp0-network-storage-client-v0.2.0"
```

Adjust only the state paths if desired. Keep the two state directories separate.

## 1. Install the passive probe in both copies

From this package directory:

```bash
python3 smml_gp0_network_storage_probe.py \
  --state-dir "$HOST_STATE" \
  install "$HOST_GAME"

python3 smml_gp0_network_storage_probe.py \
  --state-dir "$CLIENT_STATE" \
  install "$CLIENT_GAME"
```

Check both:

```bash
python3 smml_gp0_network_storage_probe.py --state-dir "$HOST_STATE" status
python3 smml_gp0_network_storage_probe.py --state-dir "$CLIENT_STATE" status
```

Expected before arming:

```text
PATCHED  Survival/Scripts/game/SurvivalGame.lua
PRESENT  Survival/Scripts/SMMLProbeNS/Probe.lua
PRESENT  Survival/Scripts/SMMLProbeNS/Runtime.lua
CONFIG   enabled=False role=disabled
```

## 2. Locate the host Save root

Only the host/A installation needs a Save snapshot.

```bash
find "$HOME/.local/share/Steam/steamapps/compatdata/387990/pfx/drive_c/users/steamuser/AppData/Roaming/Axolot Games/Scrap Mechanic/User" \
  -maxdepth 2 -type d -name Save -print
```

Use the exact `.../User/User_.../Save` path returned for the host account.

## 3. Arm host and client with the same run ID

Generate one shared ID:

```bash
RUN_ID="GP05-$(date +%Y%m%d-%H%M%S)"
echo "$RUN_ID"
```

Arm host:

```bash
python3 smml_gp0_network_storage_probe.py \
  --state-dir "$HOST_STATE" \
  arm-host \
  --run-id "$RUN_ID" \
  --save-root "/exact/host/path/to/User/User_.../Save"
```

Arm client B with exactly the same ID:

```bash
python3 smml_gp0_network_storage_probe.py \
  --state-dir "$CLIENT_STATE" \
  arm-client \
  --run-id "$RUN_ID"
```

## 4. Session 1 — network matrix + reconnect + schema 1 seed

1. Launch Steam A / Scrap Mechanic A.
2. Load the dedicated Survival test world on A.
3. **Wait at least 3 seconds before B joins.** This lets the server publish initial `setClientData` state before the new remote client exists.
4. Launch Scrap Mechanic B and join A.
5. Wait a few seconds. B automatically sends the RPC matrix.
6. When B receives the successful post-error reply, chat should display an SMML GP0 reconnect instruction.
7. On B, leave the host back to the menu while A remains in the world.
8. Wait a couple of seconds, then join A again.
9. Wait again for the automatic RPC matrix.
10. Quit B cleanly, then quit A cleanly.

Expected storage transition for this first host launch:

```text
absent -> save schema 1
```

The RPC matrix includes:

```text
N-RPC-01 valid ping
N-RPC-02 boolean payload
N-RPC-03 number payload
N-RPC-04 string payload
N-RPC-05 nested table payload
N-RPC-06 unknown contract
N-RPC-07 unsupported contract version
N-RPC-08 invalid ping payload
N-RPC-09 intentional throwing handler
N-RPC-10 valid ping after handler failure
N-RPC-11 nil envelope / local serialization behavior
```

## 5. Session 2 — persistence reload + schema migration

With the probe still armed:

1. Launch A again and load the **same** test world.
2. Wait at least 3 seconds.
3. Launch B and join A.
4. Wait for the automatic network matrix.
5. Quit B, then A cleanly.

Expected host storage transition:

```text
load schema 1 -> validate logical namespaces -> migrate -> save schema 2
```

## 6. Session 3 — schema 2 survives restart

Repeat once more:

1. Launch A and load the same world.
2. Wait at least 3 seconds.
3. B joins A and completes the automatic network matrix.
4. Quit B, then A cleanly.

Expected host storage observation:

```text
load schema 2
```

No further schema write is required.

## 7. Finish and restore

Both games must be closed.

Choose output paths:

```bash
HOST_RESULTS="/developpement/seynax/smml/smml-gp0-ns-host-$RUN_ID.zip"
CLIENT_RESULTS="/developpement/seynax/smml/smml-gp0-ns-client-$RUN_ID.zip"
COMBINED_RESULTS="/developpement/seynax/smml/smml-gp0-ns-combined-$RUN_ID.zip"
```

Finish host. This collects logs, restores/verifies the complete pre-probe Save snapshot, restores vanilla Lua/cache, and removes the probe:

```bash
python3 smml_gp0_network_storage_probe.py \
  --state-dir "$HOST_STATE" \
  finish --output "$HOST_RESULTS"
```

Finish client:

```bash
python3 smml_gp0_network_storage_probe.py \
  --state-dir "$CLIENT_STATE" \
  finish --output "$CLIENT_RESULTS"
```

Cross-correlate both sides:

```bash
python3 smml_gp0_network_storage_probe.py \
  merge-results \
  --host "$HOST_RESULTS" \
  --client "$CLIENT_RESULTS" \
  --output "$COMBINED_RESULTS"
```

The terminal prints `PASS`/`FAIL` for each GP0.5 observation. The combined ZIP contains:

```text
combined-summary.json
combined-events.json
combined-events.csv
SUMMARY.txt
```

## Required evidence scored by `merge-results`

- remote B client -> A server RPC;
- A server -> B direct response;
- A server -> all clients broadcast received by B;
- unknown contract rejection;
- unsupported version rejection;
- invalid payload rejection;
- intentional handler exception isolated, followed by a successful RPC;
- nil-envelope behavior fails open either locally or server-side;
- at least one of channels 3/4 works for `setClientData` end-to-end;
- B sees the initial client-data state after joining;
- B leave + rejoin is observed by A;
- at least three server/world creations are observed;
- storage absent -> schema 1;
- schema 1 loaded after restart -> migration -> schema 2;
- schema 2 loaded from a later game log;
- two fake SMML namespaces can use the same logical data key without collision.

## Non-destructive inspection before teardown

At any time while the games are closed, collect logs without restoring anything:

```bash
python3 smml_gp0_network_storage_probe.py \
  --state-dir "$HOST_STATE" \
  collect --output /tmp/host-preview.zip

python3 smml_gp0_network_storage_probe.py \
  --state-dir "$CLIENT_STATE" \
  collect --output /tmp/client-preview.zip
```

`collect` is read-only with respect to the game and Save.

## Recovery commands

Disable the active probe without restoring the host Save:

```bash
python3 smml_gp0_network_storage_probe.py --state-dir "$HOST_STATE" disarm
```

Restore the host Save snapshot while keeping hooks installed but disabled:

```bash
python3 smml_gp0_network_storage_probe.py --state-dir "$HOST_STATE" restore-save
```

Remove hooks after disarming/restoring:

```bash
python3 smml_gp0_network_storage_probe.py --state-dir "$HOST_STATE" uninstall
```

The normal path is `finish`.

## Deliberately out of scope for v0.2.0

- dedicated-server behavior;
- large-payload / bandwidth stress tests;
- fuzzing arbitrary userdata through the network serializer;
- channels 1 and 2 for the probe, because vanilla Survival already uses them;
- production-grade crash recovery for the installer transaction;
- a final SMML public Transport/Storage API.

The point of v0.2.0 is to establish engine behavior before those contracts are frozen.
