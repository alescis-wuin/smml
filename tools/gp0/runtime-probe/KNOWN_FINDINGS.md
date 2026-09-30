# GP0.2 — constatations runtime acquises

## v0.1.0

`dofile("$SURVIVAL_DATA/SMMLProbe/Runtime.lua")` est refusé par le moteur avec
`Invalid file location`.

Conclusion expérimentale : le runtime du probe doit être placé dans une zone
de scripts autorisée.

## v0.1.1

`$SURVIVAL_DATA/Scripts/SMMLProbe/Runtime.lua` est accepté et évalué.

L'évaluation échoue ensuite sur :

```text
attempt to call global 'rawget' (a nil value)
```

Conclusion expérimentale :

- la zone `Survival/Scripts/...` est chargeable par `dofile` dans ce contexte ;
- `rawget` n'est pas exposé par le sandbox Lua observé ;
- les probes ne doivent pas supposer la présence de toute la bibliothèque Lua
  standard ;
- l'instrumentation de production doit être fail-open.

La v0.1.3 utilise une affectation globale Lua normale et sonde explicitement
les capacités avant de les utiliser.

## v0.1.2 observed result

A Survival world loads successfully. The engine accesses
`$SURVIVAL_DATA/Scripts/SMMLProbe/Runtime.lua` and recognizes the patched scripts,
but normal-launch `print()` telemetry does not appear in `game-*.log`.

v0.1.3 therefore uses `sm.log.error` as a temporary deterministic GP0 channel.
