# GP0.5 — Vérification de restauration

Run : `GP05-20260929-153608`

Après `finish` des deux rôles :

- host : résultats collectés, snapshot `Save` restauré, probe retiré ;
- client : résultats collectés, probe retiré ;
- merge final : `PASS`.

Hash vérifié sur les deux installations :

```text
Survival/Scripts/game/SurvivalGame.lua
934beb15dff2f34638128a56aa1be8586e363bc1a5d564698e9b8f09bf9d35c4
```

Le contrôle :

```text
find <host>/Survival/Scripts/SMMLProbeNS <client>/Survival/Scripts/SMMLProbeNS -type f
```

n'a listé aucun fichier restant.

Les chemins locaux exacts et identifiants Steam du transcript d'exécution ne sont pas reproduits dans ce handoff.
