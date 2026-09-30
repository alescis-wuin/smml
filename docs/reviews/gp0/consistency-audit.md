# Audit de cohérence

## Points cohérents et renforcés

- Server-authoritative : présent dans docs initiales, code vanilla et résultats Carry.
- Cache ciblé : pratique historique + observation actuelle + bootstrapper communautaire convergent sur `core_data.cbo` pour Lua/data ; ne pas extrapoler à toutes familles.
- Baseline reconstructive : scans locaux + architecture + comparateurs externes convergent.
- Multi-entry runtime : imposé par preuve d'ordre de chargement.
- Sparse network/storage : docs officielles et conception initiale convergent.

## Contradictions / documents obsolètes

- Le dossier v1 du 28 septembre dit que la prochaine priorité principale est encore la presse/collision ; depuis, le projet a pivoté vers SMML et GP0. Il reste historique, pas état courant.
- Le cahier des charges v0.1 demande encore de « vérifier xpcall/traceback » comme ouvert ; xpcall est maintenant validé, mais `debug.traceback` est observé absent.
- `SMML_GP0_3_HOOK_MATRIX.md` marque P-HOOK-001..006 comme probes nécessaires ; plusieurs sont maintenant réalisés. Conserver le document comme design initial et superposer `GP0_STATUS.md`.
- Le résumé brut v0.1.4 `storage_matrix_complete=false` est faux par agrégation inter-world ; la matrice dédupliquée est la preuve correcte.

## Assertions à ne pas extrapoler

- globals partagés : validé sur host local, pas preuve client distant/dédié ;
- GameClass « first script » : ne signifie pas que notre code injecté au début de `SurvivalGame.lua` s'exécute avant toutes les dépendances évaluées ;
- `core_data.cbo` : causalement validé pour les scripts testés, pas cache universel ;
- Steam Verify : officiel pour vérifier les fichiers installés, mais notre preuve locale d'extras persistants interdit de l'utiliser comme preuve d'absence de résidus.
