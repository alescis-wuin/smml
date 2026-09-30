# Changelog

## v0.1.3

- Use `sm.log.error` as the primary temporary telemetry channel.
- Retain `print()` only as a last-resort fallback.
- Protect runtime loading with `pcall(dofile, ...)`.
- Protect the `server_onRefresh` runtime reload path.
- Regenerate `SHA256SUMS` from the files actually shipped.

## v0.1.2

- Runtime under `Survival/Scripts/SMMLProbe` no longer prevents Survival loading.
- Removed dependency on unavailable `rawget`/`rawset`.
- Added Lua capability probing.

## v0.1.1

- Moved runtime under the allowed `Survival/Scripts` tree.
- Collector preserves candidate logs even with zero events.

## v0.1.0

Initial passive GP0.2 runtime probe.
