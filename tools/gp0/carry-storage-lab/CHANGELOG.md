# Changelog

## v0.1.4

- Replaces the passive probe with an armed/disarmed Carry + Storage laboratory.
- Reduces vanilla hooks to SurvivalGame, SurvivalPlayer, CarryTool and
  ResourceContainer.
- Implements multi-entry idempotent runtime bootstrap.
- Adds a 16 x 13 automatic storage matrix using abortable dry transactions.
- Creates a deterministic Resource Collector + Scrap Wood CarryTool fixture.
- Adds in-game chat instructions so no handwritten test log is required.
- Adds mandatory recursive Save snapshot before world mutation.
- Adds `finish` for collect -> Save restore -> hook/cache uninstall.
- Adds automatic `storage-matrix.csv` and `carry-matrix.csv` generation.
