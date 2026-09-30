# SMML GP0.2 Carry / Storage Laboratory v0.1.4

Target: Scrap Mechanic Survival 1.0.6 build 889.

This package is a disposable research probe. It is not the future SMML runtime.
It installs four minimal vanilla hooks, snapshots the complete `Save` tree before
arming any world mutation, runs the storage matrix automatically, prepares one
deterministic CarryTool case, and produces CSV results from the game log.

## What is modified

Only these vanilla Lua files are patched, and only when their SHA-256 matches the
known clean 1.0.6.889 baseline:

- `Survival/Scripts/game/SurvivalGame.lua`
- `Survival/Scripts/game/SurvivalPlayer.lua`
- `Survival/Scripts/game/tools/CarryTool.lua`
- `Survival/Scripts/game/interactables/ResourceContainer.lua`

Owned temporary files are installed below:

- `Survival/Scripts/SMMLProbe/Runtime.lua`
- `Survival/Scripts/SMMLProbe/Lab.lua`
- `Survival/Scripts/SMMLProbe/LabData.lua`
- `Survival/Scripts/SMMLProbe/LabConfig.lua`

`Cache/Bundle/core_data.cbo` is invalidated only after its exact baseline copy
has been saved in the state directory.

## Safety model

`install` is passive. The lab cannot spawn fixtures or modify inventory until
`arm` succeeds.

`arm` requires `--save-root` and recursively copies the entire Scrap Mechanic
`Save` tree outside the game directory, hashes every copied file, verifies the
snapshot, then enables the runtime lab.

No `.db` save file is edited directly. All in-game mutation uses vanilla runtime
APIs (`sm.shape.createPart`, container transactions, player carry/inventory).

`finish` is the recommended teardown: it collects results, restores/verifies the
pre-lab `Save` snapshot, then restores all patched Lua files and `core_data.cbo`
byte-for-byte.

## Before v0.1.4

If v0.1.3 is still installed, uninstall it first with its own script/state-dir.
The v0.1.4 preflight intentionally refuses already modified core files.

## Install hooks

```bash
python3 smml_gp0_lab.py \
  --state-dir "/developpement/seynax/smml-gp0-carry-storage-lab-state-v0.1.4" \
  install \
  "/home/seynax/.local/share/Steam/steamapps/common/Scrap Mechanic/"
```

Check:

```bash
python3 smml_gp0_lab.py \
  --state-dir "/developpement/seynax/smml-gp0-carry-storage-lab-state-v0.1.4" \
  status
```

Expected before arming: four `PATCHED`, three runtime files `PRESENT`,
`CONFIG enabled=False`, and `core_data.cbo absent`.

## Locate the Save root

The Windows-side path observed by Scrap Mechanic is under:

```text
C:/users/steamuser/AppData/Roaming/Axolot Games/Scrap Mechanic/User/User_*/Save
```

On Proton, a safe way to locate the corresponding Linux directory without
hard-coding a Steam user identifier is:

```bash
find "$HOME/.local/share/Steam/steamapps/compatdata" \
  -type d \
  -path '*/pfx/drive_c/users/steamuser/AppData/Roaming/Axolot Games/Scrap Mechanic/User/User_*/Save' \
  -print
```

Use the exact `Save` directory returned by that command as `--save-root`.

## Arm the lab

Scrap Mechanic must be closed.

```bash
python3 smml_gp0_lab.py \
  --state-dir "/developpement/seynax/smml-gp0-carry-storage-lab-state-v0.1.4" \
  arm \
  --save-root "/exact/path/to/.../User/User_.../Save"
```

This is the point at which the recursive pre-test Save snapshot is created.

## In-game test flow

Launch Scrap Mechanic normally, without `-dev`, and enter or create the dedicated
Survival test world.

The lab then performs the following automatically:

1. waits until the joined player's character exists;
2. creates the 16 storage fixtures in a 4x4 grid in front of the player;
3. waits for each engine/scripted container to expose container slot 0;
4. runs 16 x 13 = 208 storage acceptance cases;
5. each storage case is a dry transaction:
   `canCollect -> beginTransaction -> collect(..., false) -> abortTransaction`;
6. verifies that abort left the fixture quantity unchanged;
7. adds a compact manual verification loadout to the player inventory when space
   permits;
8. creates a green Resource Collector near the player;
9. loads one Scrap Wood into the player's Carry container;
10. displays a chat instruction.

The only required manual Carry action is:

```text
aim at the GREEN Resource Collector -> press Insert once
```

The probe then records:

```text
cl_tryInsert
raycast target
ContainerInsertTargets decision
canCollect decision
client sv_n_sendItem request
server sv_n_sendItem reception
ResourceContainer.sv_e_receiveItem reception
Carry quantity after transfer
Resource Collector quantity after transfer
```

When the final quantities prove the transfer, the game displays:

```text
[SMML GP0] test Carry valide...
```

At that point you may open a few of the 16 containers for visual/manual spot
checks, then quit the game cleanly. No handwritten matrix is required.

## Collect only

If you want to inspect results before restoring anything:

```bash
python3 smml_gp0_lab.py \
  --state-dir "/developpement/seynax/smml-gp0-carry-storage-lab-state-v0.1.4" \
  collect \
  --output "/developpement/seynax/smml/smml-gp0-carry-storage-lab-results-v0.1.4.zip"
```

The result ZIP contains, when available:

- `summary.json`
- `events.json`
- `events.csv`
- `storage-matrix.csv`
- `carry-matrix.csv`
- `probe-lines.txt`
- `diagnostic-lines.txt`
- `snapshot-manifest.json`
- candidate raw game logs

A complete automatic storage pass is exactly 208 `storage.case` rows.

## Recommended one-command teardown

After the game is closed:

```bash
python3 smml_gp0_lab.py \
  --state-dir "/developpement/seynax/smml-gp0-carry-storage-lab-state-v0.1.4" \
  finish \
  --output "/developpement/seynax/smml/smml-gp0-carry-storage-lab-results-v0.1.4.zip"
```

`finish` performs, in this order:

1. collect results;
2. verify the pre-lab Save snapshot;
3. quarantine the post-lab Save tree;
4. restore the pre-lab Save tree;
5. verify restored Save files against their hashes;
6. disable/remove the lab runtime;
7. restore the four vanilla Lua files byte-for-byte;
8. quarantine any rebuilt `core_data.cbo`;
9. restore the exact baseline `core_data.cbo`;
10. verify all restored hashes.

## Separate recovery commands

Disable the lab but intentionally keep Save changes:

```bash
python3 smml_gp0_lab.py --state-dir "..." disarm
```

Restore the Save snapshot but keep hooks installed/disarmed:

```bash
python3 smml_gp0_lab.py --state-dir "..." restore-save
```

Remove hooks after the lab is disarmed:

```bash
python3 smml_gp0_lab.py --state-dir "..." uninstall
```

`uninstall` refuses while the lab is armed.
