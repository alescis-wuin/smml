# Architecture cible SMML

## Séparation des responsabilités

### Manager
UI/CLI, profils, opérations utilisateur, launch assist optionnel mais **sans modifier les Steam Launch Options automatiquement**.

### Resolver
Pur moteur de résolution : packages, SemVer, dépendances dures/molles, capacités, conflits, ordre, lockfile. Aucune écriture jeu.

### State Manager / Transaction Engine
Préflight, baselines, snapshots utilisateurs, staging, journal, commit, rollback, drift, recovery.

### Hook Patcher
- Engine générique : parse/anchor/transform/verify.
- Hook Definition Pack par build : hashes attendus, ancres, transformations minimales, contrats fournis.
- Vanilla ne contient que des appels minimaux vers l'adapter/runtime.

### Content Composer
Reconstruit les fichiers partagés à partir d'une baseline + contributions déclaratives résolues. Chaque sortie possède provenance et ownership.

### Runtime Adapter/Core
Traduit les callbacks/objets fragiles du jeu vers l'API stable. C'est le seul endroit qui connaît la forme détaillée des hooks vanilla.

### Modding API
Petits contrats versionnés, services serveur/client, pas de dépendance aux noms de fichiers vanilla.

### SDK
Event bus, queues, scheduler, machines à états, helpers ; optionnel pour éviter de gonfler le noyau.

## Bootstrap runtime établi

La preuve v0.1.3/v0.1.4 montre qu'un bootstrap injecté uniquement dans `SurvivalGame.lua` est trop tardif pour certains fichiers évalués auparavant. Architecture cible :

```lua
-- conceptuel dans chaque point d'entrée minimal
SMML_EnsureRuntime()
-- puis appel adapter/hook si runtime présent
```

Le chargement doit être idempotent, fail-open sur l'initialisation du probe mais **fail-closed pour une installation de production incompatible** : une erreur de plateforme doit être visible et empêcher un état partiellement composé, sans faire disparaître le diagnostic.

## Hot paths

Ne pas exporter tous les callbacks moteur. Les événements très fréquents (`server_onFixedUpdate`, `client_onUpdate`, etc.) ne deviennent contrats publics que si un besoin concret existe, avec budget et éventuellement agrégation/sampling.

## Native / VFS

Les projets Rivet/CarbonLauncher démontrent qu'une approche DLL/hooking est possible dans l'écosystème Scrap Mechanic. Elle est volontairement différée : coût de compatibilité, sécurité et maintenance plus élevé ; SMML doit d'abord prouver la valeur de la composition Lua/data. Une abstraction `InstallBackend`/`RuntimeBackend` doit toutefois éviter de rendre une évolution future impossible.
