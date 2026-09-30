# Transaction Preparer

Reference CLI for `TransactionEngine v1 — non-destructive core`.

It consumes a valid `TransactionJournal v1` in phase `PLANNED`, verifies the live game is still in every operation's `before` state, captures rollback bytes, imports desired `after` bytes, writes a durable staging manifest, then atomically advances the persistent journal to `PREPARED`.

It **does not mutate the game root**.

```bash
mkdir -p "$HOME/.local/state/smml"

python tools/gp1/transaction-preparer/smml_transaction_prepare.py \
  --journal-plan artifacts/transaction-journal.planned.json \
  --game-root "$HOME/.local/share/Steam/steamapps/common/Scrap Mechanic" \
  --game-target artifacts/game-target.json \
  --after-root artifacts/desired-game-tree \
  --state-root "$HOME/.local/state/smml"
```

`--after-root` is required only when at least one operation creates or replaces a file. It is read-only and must be outside the game root.

Persistent output:

```text
<state-root>/transactions/<transaction-id>/
├── journal.json
└── staging/
    ├── manifest.json
    └── blobs/sha256/<prefix>/<digest>
```

Running the same preparation again after a successful `PREPARED` state is idempotent: the manifest and every referenced blob are revalidated and no journal revision is added.
