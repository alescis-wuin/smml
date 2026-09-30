# Comparatif des approches de modding pertinentes

| Approche | Forces | Risques / différence SMML | Leçon |
|---|---|---|---|
| File mods historiques | simples, directs | collisions, overwrite, uninstall fragile | à migrer vers Composer |
| Scrap Mechanic Bootstrapper | composition shared files, conflits, cache ciblé | wrapper Steam/Windows, scope encore expérimental | validation forte du concept Composer |
| Scrap Mechanic Mod Manager | UX in-game, framework direct Survival | patchs multiples, incident terrain 1.4.6 | contributions conditionnelles atomiques |
| ScrapLab | backup-first, guards exacts | peut éditer les saves, hors invariant SMML | bonnes pratiques recovery |
| Rivet/CarbonLauncher | hooks natifs, APIs partagées | compatibilité binaire, sécurité, maintenance | backend futur possible |
| BepInEx (analogie) | IDs, SemVer, deps, loader mature | Unity-specific, pas Scrap Mechanic | modèle de manifest/resolver |
| OSTree (analogie) | immutable trees, rollback, reconstructif | OS deployment, beaucoup plus général | modèle BaselineVault |
