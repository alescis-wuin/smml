# SMML — TransactionEngine v1 — non-destructive core

Staging manifest schema: `smml.transaction-staging-manifest/1`  
JSON Schema: `urn:smml:schema:transaction-staging-manifest:1`

## 1. Scope

This slice implements the non-destructive foundation of `TransactionEngine`.

It provides:

- a transaction-local content-addressed `StagingStore` outside the game root;
- a durable atomic `JournalStore` for `TransactionJournal v1`;
- preparation of a validated `PLANNED` journal into `PREPARED`;
- capture of every present `before` state required for rollback;
- import of every present `after` state required for commit;
- a durable staging manifest binding staged bytes to journal operations;
- idempotent resume of preparation after interruption;
- fault injection around durable state publication.

It still performs **no mutation of the game root**. Commit, verify and rollback execution remain deferred.

## 2. Trust boundaries

Three roots are distinct:

- `gameRoot`: live Scrap Mechanic installation, read-only in this slice;
- `afterRoot`: generated desired outputs, read-only in this slice;
- `stateRoot`: trusted SMML persistent state, writable and MUST be outside `gameRoot`.

`stateRoot` MUST already exist and MUST be a real directory, not a symlink/reparse point. The reference implementation does not claim multi-process safety yet; the inter-process lock remains a later P0 item.

`afterRoot` MUST also be a real directory outside `gameRoot`. Every requested file is opened without following links and is revalidated while read.

## 3. Persistent layout

For transaction `tx-example`:

```text
<stateRoot>/
└── transactions/
    └── tx-example/
        ├── journal.json
        └── staging/
            ├── manifest.json
            └── blobs/
                └── sha256/
                    └── ab/
                        └── abcdef...64hex
```

The blob path is derived solely from its lowercase SHA-256:

```text
staging/blobs/sha256/<first-two-hex>/<full-sha256>
```

No absolute local path is serialized in the staging manifest.

## 4. StagingStore

Blobs are exact bytes addressed by SHA-256.

For every insertion the store MUST:

1. calculate SHA-256 from exact bytes;
2. reject a digest different from the expected journal state;
3. publish the blob atomically in the transaction staging directory;
4. make the published file durable according to the reference platform policy;
5. reopen/re-hash the final blob;
6. reject any existing blob whose bytes do not match its path digest.

Insertion is idempotent when a valid blob already exists.

The staging store MUST retain:

- every present `after` state until commit/recovery no longer needs it;
- every present `before` state until rollback/recovery no longer needs it.

A hash without recoverable bytes is not sufficient to enter `PREPARED`.

## 5. Staging manifest

`smml.transaction-staging-manifest/1` binds the durable blobs to one transaction and the journal revision that enters `PREPARED`.

For each operation it stores the logical path and staged `before`/`after` state. A present state includes:

- exact SHA-256;
- exact size.

`blobs` is the unique ASCII-sorted set of every digest referenced by a present state. No unreferenced blob record is allowed in the manifest.

The manifest is not an authorization to mutate the game. It is evidence that required bytes were made durable before the `PREPARED` journal revision.

## 6. JournalStore durability

Every journal publication uses a sibling temporary file and whole-file replacement:

```text
serialize validated full journal
→ create sibling temp
→ write all bytes
→ fsync(temp)
→ atomic replace journal.json
→ fsync(parent directory) where supported
```

Every newly created directory in the transaction/staging layout is itself made durable by syncing its parent directory before later durable files depend on that path. On the validated POSIX reference environment, inability to open/fsync the relevant directory is a hard failure rather than a best-effort warning.

A journal reader MUST reject a symlink/reparse point and MUST parse a complete JSON document before returning it.

A rewrite additionally enforces:

- transaction ID unchanged;
- `createdAt` unchanged;
- embedded `gameTarget` unchanged;
- operation identity/path/kind/owner/before/after unchanged;
- revision increments by exactly one;
- incidents are append-only;
- phase history is unchanged for same-phase acknowledgements, or appended exactly once for a phase transition;
- operation status never changes backwards except through the explicit recovery/rollback model implemented by a later engine slice.

For this preparation slice the only emitted rewrite is:

```text
PLANNED revision N
→ PREPARED revision N+1
```

with all operation statuses still `PENDING`.

## 7. Preparation algorithm

Input is a valid `TransactionJournal v1` in phase `PLANNED`. In this slice the journal itself is the transaction plan; no second plan format duplicates the same fields.

Preparation is:

```text
validate PLANNED journal
validate fresh GameTarget binding
validate gameRoot / afterRoot / stateRoot boundaries

persist PLANNED journal durably if absent

for each operation in sequence:
    observe gameRoot path read-only
    require physical classification BEFORE
    if before.exists:
        stable-read current game bytes
        require before SHA-256
        stage before blob

    if after.exists:
        stable-read afterRoot/<logical path>
        require after SHA-256
        stage after blob

build + validate staging manifest
persist staging manifest durably

rewrite journal:
    journalRevision += 1
    phase = PREPARED
    append PREPARED phaseHistory entry
    all statuses remain PENDING
persist PREPARED journal durably
```

Only the final durable `PREPARED` journal revision states that preparation completed.

## 8. Idempotent resume

A repeated preparation request for the same transaction is allowed when persistent state is either:

- `PLANNED`: staging is verified/rebuilt idempotently and preparation continues;
- `PREPARED`: staging manifest and every referenced blob are revalidated, then preparation returns without a new journal revision.

If the persistent journal differs in immutable transaction content, or is in another phase, preparation fails closed.

Stale temporary files from interrupted atomic publications are not authoritative and may be removed before a later publication.

## 9. Fault injection

The reference implementation exposes named fault points around non-destructive persistence, including:

- after temporary file `fsync`;
- after atomic replacement but before directory durability;
- after blob publication;
- after staging-manifest publication;
- after the `PLANNED` journal is durable;
- immediately before and after the `PREPARED` journal publication.

Tests MUST prove that injected failure leaves the authoritative JSON file either absent, at the complete previous revision, or at the complete new revision. Partial JSON is never accepted as a valid state.

These tests cover durability infrastructure only. Fault injection around actual game mutations remains mandatory before destructive commit/rollback is enabled.

## 10. Deferred

Still outside this slice:

- mutation of `gameRoot`;
- transition to `COMMITTING`;
- commit of create/replace/delete;
- `APPLIED` acknowledgements;
- transition to `VERIFYING` and `VERIFIED` acknowledgements;
- rollback execution;
- BaselineVault / StateManifest ownership integration;
- inter-process lock;
- Windows-specific durability proof (`FlushFileBuffers`, directory semantics);
- destructive fault injection.

The next destructive slice MUST consume this durable staging/journal state rather than inventing another persistence model.
