# SMML — TransactionJournal v1

Schema identifier: `smml.transaction-journal/1`  
JSON Schema: `urn:smml:schema:transaction-journal:1`

## 1. Scope

`TransactionJournal` is the durable write-ahead record for one SMML filesystem transaction.

Its v1 purpose is to make a transaction:

- auditable;
- recoverable after process crash or power loss;
- rollback-capable;
- diagnosable;
- fail-closed when the observed filesystem does not match an expected state.

V1 journals **regular-file mutations only**. Directory ownership/removal, symlink/reparse-point handling, filesystem locking and OS-specific durability are Transaction Engine / PathPolicy responsibilities. An unexpected non-file object observed at a managed file path is recorded as an incident and MUST be treated as foreign state.

## 2. Source-derived constraints

The GP0 handoff establishes the following requirements:

1. nominal transaction phases are:

   `PLANNED -> PREPARED -> COMMITTING -> VERIFYING -> COMMITTED`;

2. incident phases include:

   `RECOVERY_REQUIRED`, `FOREIGN_MODIFICATION`, `ROLLBACK_REQUIRED`, `FAILED`;

3. every file mutation records expected existence before/after and hashes before/after when the file exists;

4. recovery MUST classify the current object against the expected before/after states and MUST NOT guess;

5. the journal must be durable before the mutations it describes;

6. rollback must be idempotent;

7. paths and persistent local state are not trusted merely because they came from a prior SMML run.

## 3. V1 design decisions

### 3.1 Embedded target snapshot

Every journal embeds the `smml.game-target/1` snapshot used to plan the transaction. The snapshot is immutable for the lifetime of the transaction.

The Transaction Engine MUST still re-inspect the installation and preconditions before mutating. Embedding the target does not make the journal authoritative over the filesystem.

### 3.2 Mutation kinds

V1 uses exactly three filesystem mutation kinds:

- `create` — file absent before, present after;
- `replace` — file present before and after, with a different SHA-256;
- `delete` — file present before, absent after.

Business-level actions such as `compose`, `install`, `uninstall` or `hook` are not filesystem mutation kinds. Their attribution is represented by `owner`; richer provenance belongs to later manifests/state models.

### 3.3 File states

A file state is:

```json
{ "exists": false }
```

or:

```json
{ "exists": true, "sha256": "<64 lowercase hex>" }
```

Les champs `sha256` décrivent le SHA-256 des octets exacts du fichier selon [`hashing.md`](hashing.md). Ils ne sont jamais calculés à partir d'une représentation texte normalisée.

A present file without a SHA-256 is invalid. An absent file with a SHA-256 is invalid.

### 3.4 Operation order

`sequence` is zero-based, unique and contiguous. `operations` MUST be stored in exactly that order.

The Transaction Engine commits and verifies operations in ascending `sequence` order. Rollback, when required, is performed in reverse order for operations that were actually applied.

### 3.5 Operation status

Operation status is the **last durable knowledge recorded by SMML**, not a substitute for observing the filesystem.

Statuses are:

- `PENDING` — journal has not durably recorded the mutation as applied;
- `APPLIED` — mutation was applied and that fact was durably recorded;
- `VERIFIED` — after-state was re-read and verified;
- `ROLLED_BACK` — before-state was restored and that fact was durably recorded.

A crash may occur after a filesystem mutation becomes durable but before the corresponding status update. Recovery therefore MUST classify actual filesystem state independently of `status`.

### 3.6 Revision

`journalRevision` is a monotonically increasing integer. It increments for every durable journal rewrite, including operation-status updates even when `phase` does not change.

The v1 engine SHOULD durably record an operation as `APPLIED` before mutating the next operation. This bounds normal commit progress to at most one filesystem mutation ahead of the durable per-operation status record.

### 3.7 Phase history

`phaseHistory` records phase transitions only. It is append-only in the logical model.

- first entry MUST be revision `0`, phase `PLANNED`;
- revisions MUST be strictly increasing;
- the final entry phase MUST equal top-level `phase`;
- all history revisions MUST be `<= journalRevision`.

Permitted phase transitions:

```text
PLANNED
  -> PREPARED | FAILED

PREPARED
  -> COMMITTING | RECOVERY_REQUIRED | FOREIGN_MODIFICATION | FAILED

COMMITTING
  -> VERIFYING | RECOVERY_REQUIRED | FOREIGN_MODIFICATION | ROLLBACK_REQUIRED | FAILED

VERIFYING
  -> COMMITTED | RECOVERY_REQUIRED | FOREIGN_MODIFICATION | ROLLBACK_REQUIRED | FAILED

RECOVERY_REQUIRED
  -> COMMITTING | VERIFYING | FOREIGN_MODIFICATION | ROLLBACK_REQUIRED | FAILED

FOREIGN_MODIFICATION
  -> RECOVERY_REQUIRED | ROLLBACK_REQUIRED | FAILED

ROLLBACK_REQUIRED
  -> RECOVERY_REQUIRED | FOREIGN_MODIFICATION | FAILED

COMMITTED
  -> terminal

FAILED
  -> terminal
```

No transition may silently skip `PREPARED`, `COMMITTING` or `VERIFYING` on the successful path.

### 3.8 Incidents

`incidents` is an append-only audit list in the logical model. Incident categories are aligned with the incident transaction phases:

- `RECOVERY_REQUIRED`;
- `FOREIGN_MODIFICATION`;
- `ROLLBACK_REQUIRED`;
- `FAILED`.

`reasonCode` is an extensible machine-readable uppercase identifier. The schema deliberately does not freeze a global reason-code vocabulary yet.

When the current `phase` is an incident phase, the most recent incident MUST have the same `kind`.

`observed` can record:

- `missing`;
- `file` plus SHA-256;
- `directory`;
- `symlink`;
- `reparsePoint`;
- `other`.

SMML MUST NOT follow an unexpected symlink/reparse point merely to obtain a hash.

## 4. Nominal phase invariants

### `PLANNED`

- all operations are `PENDING`;
- no filesystem mutation may have been started by this transaction.

### `PREPARED`

The transition to `PREPARED` means, at minimum:

- final preflight passed;
- required save snapshot policy was satisfied by the surrounding Transaction Engine when applicable;
- outputs needed by the transaction were staged or are otherwise recoverably reproducible;
- staged hashes were validated;
- the `PREPARED` journal revision is durable.

All operations remain `PENDING`.

### `COMMITTING`

The `COMMITTING` phase MUST be durable before operation 0 is mutated.

In a normal non-recovery commit, `APPLIED` operations form a contiguous prefix of `operations`; remaining operations are `PENDING`.

### `VERIFYING`

All filesystem mutations have been attempted. Operations are `APPLIED` or `VERIFIED`. In normal verification, `VERIFIED` operations form a contiguous prefix.

### `COMMITTED`

All operations are `VERIFIED`. `COMMITTED` is terminal.

## 5. Recovery classifier

For each operation, recovery compares the actual object at `path` with `before` and `after`.

For a regular file state:

```text
actual == before -> BEFORE
actual == after  -> AFTER
anything else    -> FOREIGN
```

Equality includes both existence and SHA-256 when present.

Consequences:

- `BEFORE` means the operation is not currently reflected in the filesystem;
- `AFTER` means the operation is currently reflected in the filesystem;
- `FOREIGN` means SMML MUST stop destructive progress for that path and enter `FOREIGN_MODIFICATION` or another fail-closed incident state.

The classifier is authoritative over stale operation status.

### Examples

Create:

```text
before absent, current absent      -> BEFORE
before absent, current afterHash   -> AFTER
before absent, current other file  -> FOREIGN
```

Replace:

```text
current beforeHash -> BEFORE
current afterHash  -> AFTER
current otherHash  -> FOREIGN
missing            -> FOREIGN
```

Delete:

```text
current beforeHash -> BEFORE
missing            -> AFTER
current otherHash  -> FOREIGN
```

## 6. Journal write ordering

V1 distinguishes **write-ahead authorization** from **post-action acknowledgement**.

A journal revision that authorizes a future destructive action MUST be durable before that action starts. In particular, `COMMITTING` MUST be durable before operation 0, and `ROLLBACK_REQUIRED` MUST be durable before rollback starts. Durability means the new journal file has been flushed, atomically published and its directory entry made durable where required by the platform.

Conversely, an operation status such as `APPLIED`, `VERIFIED` or `ROLLED_BACK` is a post-action acknowledgement: it is written only after the corresponding filesystem state has itself been made durable and re-observed as required.

Exact POSIX/Windows primitives belong to `IAtomicFilesystem` and are not specified by this JSON format.

For commit:

```text
PREPARED durable
COMMITTING durable
mutate op N
make destination mutation durable according to platform policy
record op N = APPLIED durably
only then continue to op N+1
```

For verification:

```text
VERIFYING durable
verify op N from filesystem
record op N = VERIFIED durably
continue
all verified
COMMITTED durable
```

## 7. Rollback invariant

Rollback is not permitted to overwrite arbitrary current state.

For an operation considered applied, rollback may restore `before` only when the current object still matches `after`. If current state matches neither expected side, rollback MUST stop fail-closed.

After restoring `before`, the engine re-reads the object and only then records `ROLLED_BACK` durably.


## 7.1 Content availability invariant

Hashes identify expected bytes but do not store those bytes. Therefore the surrounding Transaction Engine MUST guarantee content availability until the transaction no longer needs recovery:

- every present `after` state must be available from durable staging or be deterministically reproducible and revalidated to the recorded SHA-256 before use;
- every present `before` state that may need rollback must remain recoverably available, for example through the Baseline Vault, a managed-state content store, or transaction-local durable backup;
- the physical reference/storage format is deliberately not frozen by `TransactionJournal v1`.

A journal whose required before/after bytes cannot be recovered MUST enter a fail-closed incident state rather than fabricate content.

## 8. Path requirements

Journal paths are logical paths relative to the game root:

- `/` separator;
- no absolute paths;
- no drive-absolute paths;
- no `.` or `..` segments;
- no backslashes;
- no NUL;
- no duplicate case-insensitive targets inside one journal.

This is a minimum journal invariant. Future `PathPolicy` remains responsible for platform-specific reserved names, normalization/case rules, root containment, symlink/reparse-point validation and other filesystem policy.

## 9. Semantic validation beyond JSON Schema

A conforming v1 validator MUST additionally enforce:

1. unique `operationId` values;
2. unique and contiguous `sequence = 0..N-1` matching array order;
3. no case-insensitive path collisions;
4. `kind` consistent with before/after existence;
5. `replace` before/after hashes differ;
6. phase/status coherence;
7. `APPLIED` prefix in normal `COMMITTING`;
8. `VERIFIED` prefix in normal `VERIFYING`;
9. valid phase transitions in `phaseHistory`;
10. unique incident IDs;
11. incident references only existing operation IDs;
12. incident revisions not greater than `journalRevision`;
13. an incident current phase has a matching latest incident kind;
14. timestamps are nondecreasing and `createdAt <= updatedAt`.

## 10. Explicit v1 non-goals / open design items

V1 does not yet freeze:

- directory mutation journaling;
- State Manifest schema or before/after global state digests;
- package/profile/lockfile provenance fields;
- staging directory physical layout;
- OS-specific fsync/rename implementation;
- lock-file format;
- save snapshot journal schema;
- cryptographic authentication of a locally tampered journal;
- a closed registry of incident reason codes.

These omissions are deliberate. They must not be silently inferred by an implementation.

## 11. Security interpretation of journal metadata

`owner`, operation status, phase history and incident diagnostics are audit/recovery metadata. They MUST NOT by themselves authorize a destructive write or delete.

Before a mutation, the Transaction Engine revalidates:

- the embedded `GameTargetIdentity` both structurally and semantically;
- root containment and PathPolicy;
- object type / symlink / reparse-point constraints;
- current before/after classification;
- any State Manifest ownership rule applicable to the operation.

A locally edited journal therefore does not become an authority merely because it passes JSON Schema validation.

## 12. Reference recovery vectors

`tests/recovery_vectors.json` contains machine-readable v1 vectors for:

- crash before operation 0;
- mutation applied before its status update;
- multiple applied operations with a stale frontier;
- all mutations present before verification;
- foreign hash detection;
- impossible non-prefix commit state;
- symlink substitution at a managed path.

These vectors exercise the recovery rule independently from persisted operation `status`.
