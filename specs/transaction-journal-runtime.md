# SMML — TransactionJournal runtime integration v1

Runtime report schema: `smml.transaction-recovery-report/1`  
JSON Schema: `urn:smml:schema:transaction-recovery-report:1`

## 1. Scope

This stage connects `TransactionJournal v1` to the real filesystem **without mutating the game installation**.

It provides:

- no-follow observation of every journal operation path;
- exact SHA-256 acquisition for regular files;
- `BEFORE | AFTER | FOREIGN` classification from observed state;
- fail-closed path-safety checks for symlink, reparse point, hardlink and case mismatch;
- binding of the embedded journal target to a freshly produced `GameTargetIdentity`;
- phase-aware recovery diagnostics;
- a machine-readable recovery report and CLI.

It explicitly does **not** provide commit, rollback, journal rewrites, staging publication, baseline restoration, ownership mutation, locking or save mutation.

## 2. Read-only boundary

The recovery inspector MUST NOT write under the supplied game root.

The reference CLI:

- only opens game files for reading;
- never updates the journal;
- never changes operation status or phase;
- never creates staging data in the game tree;
- refuses an `--output` path located inside the game root;
- writes to stdout when no output path is requested.

A recovery decision such as `RESUME_COMMIT` or `ROLLBACK_REQUIRED` is diagnostic only. It is not authorization and it does not execute that action.

## 3. Filesystem observation

For every operation path, the inspector validates the logical path with `PathPolicy v1` and traverses the game root without following links on the validated POSIX reference environment.

Observation kinds are:

- `missing`;
- `file`;
- `directory`;
- `symlink`;
- `reparsePoint`;
- `other`.

A regular file observation includes:

- exact byte SHA-256;
- size;
- hardlink count;
- `stable: true` only after metadata before/after hashing matches.

If a file changes while it is being hashed, the inspection fails with `TXR_UNSTABLE_OBSERVATION`; no recovery decision is emitted from a mixed snapshot.

### 3.1 Path-safety blocking

The report can mark an observation `pathSafety.status = BLOCKED` for:

- `ANCESTOR_MISSING`;
- `ANCESTOR_NOT_DIRECTORY`;
- `CASE_MISMATCH`;
- `SYMLINK_FORBIDDEN`;
- `REPARSE_POINT_FORBIDDEN`;
- `HARDLINK_FORBIDDEN`.

A blocked path forces the overall decision `PATH_POLICY_BLOCKED` unless the target binding already fails, in which case `TARGET_MISMATCH` has precedence.

Hardlinks are safe to observe, but `replace` and `delete` against a regular file with `linkCount != 1` are blocked because `PathPolicy v1` forbids mutating hardlinked files.

## 4. Target binding

The journal embeds a historical `GameTargetIdentity`. Runtime recovery takes a fresh `GameTargetIdentity` produced for the supplied game root and compares:

- Steam AppID;
- game version;
- engine build;
- Steam build ID and branch;
- host/game OS and architecture;
- compatibility-layer kind;
- content-tree algorithm;
- canonical policy identifier;
- complete canonical fingerprint summary;
- every strict target fingerprint present in the journal snapshot.

The following fields are deliberately **not** required to remain equal:

- `installationExactFingerprint`;
- `rootFingerprints`.

This is required by the proven `Cache/` drift: canonical policy v2 excludes rebuildable cache while `Cache/Bundle/core_data.cbo` remains a strict target fingerprint.

A mismatch forces `TARGET_MISMATCH`. The report may still contain read-only path observations, but no resume/rollback recommendation is considered actionable.

## 5. Content classifier

For each operation, the actual observation is converted to the existing `TransactionJournal v1` classifier:

```text
actual == before -> BEFORE
actual == after  -> AFTER
otherwise        -> FOREIGN
```

The journal operation `status` is not used as proof. It is compared only after physical classification to produce a diagnostic assessment:

- `MATCHES_OBSERVED_STATE`;
- `STALE_STATUS` — notably `PENDING` while bytes already equal `after`;
- `STATE_REGRESSED`;
- `FOREIGN`.

## 6. Phase-aware recovery decision

### `PLANNED` / `PREPARED`

- all `BEFORE` -> `NO_RECOVERY_NEEDED`;
- any `AFTER` with no foreign object -> `RECOVERY_REQUIRED`;
- any `FOREIGN` -> `FOREIGN_MODIFICATION`.

An `AFTER` state here is not treated as authorization: `COMMITTING` should have been durable before mutation began.

### `COMMITTING` / `RECOVERY_REQUIRED`

The sequential frontier is reconstructed from bytes:

```text
AFTER* BEFORE* -> RESUME_COMMIT(nextSequence = first BEFORE)
AFTER+         -> READY_TO_VERIFY
BEFORE ... AFTER -> RECOVERY_REQUIRED
FOREIGN anywhere -> FOREIGN_MODIFICATION
```

### `VERIFYING`

- all `AFTER` -> `READY_TO_VERIFY`;
- otherwise -> `RECOVERY_REQUIRED` or `FOREIGN_MODIFICATION`.

### `ROLLBACK_REQUIRED`

Each path is evaluated idempotently:

- `AFTER` -> can be rolled back later;
- `BEFORE` -> already rolled back;
- `FOREIGN` -> stop.

The report emits `rollbackSequences` in descending order but performs no rollback.

### `FOREIGN_MODIFICATION`

If the physical foreign state disappeared, the inspector returns `RECOVERY_REQUIRED`; it does not silently resume a transaction from an incident journal.

### Terminal phases

- `COMMITTED` with all `AFTER` -> `TERMINAL_COMMITTED`;
- a drifted committed state -> `FOREIGN_MODIFICATION`;
- `FAILED` -> `TERMINAL_FAILED`.

## 7. Recovery report

`smml.transaction-recovery-report/1` is a diagnostic artifact. It contains no absolute game-root path.

It records:

- transaction and journal revision/phase;
- inspection timestamp;
- target binding result;
- physical observation and classifier result for each operation;
- status-vs-filesystem assessment;
- aggregate counts;
- a single phase-aware recovery decision.

The report is intentionally not a journal revision and MUST never be used as a substitute for the durable journal.

## 8. Reference CLI

```bash
python tools/gp1/transaction-recovery-inspector/smml_transaction_recovery_inspector.py \
  --journal artifacts/transaction-journal.json \
  --game-root "$HOME/.local/share/Steam/steamapps/common/Scrap Mechanic" \
  --game-target artifacts/game-target.json \
  --output artifacts/transaction-recovery-report.json
```

Exit status:

- `0`: a report was produced and no fail-closed blocker was found;
- `2`: report produced, but decision is `TARGET_MISMATCH`, `PATH_POLICY_BLOCKED`, `FOREIGN_MODIFICATION` or `RECOVERY_REQUIRED`;
- `1`: invalid input/schema or observation failure.

## 9. TransactionEngine handoff

`TransactionEngine v1 — non-destructive core` now implements the first three deferred foundations in [`transaction-engine.md`](transaction-engine.md): transaction-local staging/CAS, durable atomic journal persistence on the validated POSIX reference environment, and the write-ahead transition `PLANNED -> PREPARED`.

Still deferred after that slice:

- inter-process transaction locks;
- transition to `COMMITTING`;
- commit operations against the game root;
- `APPLIED` acknowledgements;
- verification writes and `VERIFIED` acknowledgements;
- rollback execution;
- ownership/state manifest integration;
- Windows-specific durability proof (`FlushFileBuffers`, directory semantics);
- fault injection around destructive actions.

The read-only recovery report remains diagnostic only and does not become an authorization merely because durable staging exists.
