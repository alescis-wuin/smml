# Changelog

## 0.2.0 — 2026-09-29

- Added dedicated GP0.5 host/client roles with a shared run ID.
- Reduced vanilla mutation surface to `SurvivalGame.lua` only.
- Added real remote-client RPC matrix and server direct/broadcast replies.
- Added unknown-contract, version, invalid-payload, handler-throw and nil-envelope tests.
- Added `setClientData` probes for channels 3 and 4 without touching vanilla channels 1/2.
- Added player join/leave and server lifecycle evidence.
- Added three-session `sm.storage` seed/migrate/reload sequence.
- Added explicit logical namespace collision test for two fake SMML mods.
- Added host-only recursive Save snapshot/restore and per-install cache restoration.
- Added host/client result ZIP merger with GP0.5 PASS/FAIL checks.
