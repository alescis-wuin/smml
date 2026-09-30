# Transaction Recovery Inspector

Read-only reference CLI for `TransactionJournal runtime integration v1`.

It never mutates the game root or journal. A recovery decision is diagnostic only.

```bash
python tools/gp1/transaction-recovery-inspector/smml_transaction_recovery_inspector.py \
  --journal artifacts/transaction-journal.json \
  --game-root "$HOME/.local/share/Steam/steamapps/common/Scrap Mechanic" \
  --game-target artifacts/game-target.json \
  --output artifacts/transaction-recovery-report.json
```

Omit `--output` to emit JSON to stdout. An output path inside `--game-root` is rejected.

Exit codes:

- `0`: report produced without a fail-closed blocker;
- `2`: report produced but recovery is blocked or requires explicit recovery handling;
- `1`: invalid input/schema or observation failure.
