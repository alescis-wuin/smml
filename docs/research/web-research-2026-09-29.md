# Recherche externe consolidée — 2026-09-29

## Sources officielles Axolot

### Lua / debug

Scrap Mechanic documente Lua 5.1 et recommande `-dev` pour console/hot reload. La documentation de `print` et notre expérience v0.1.2 convergent : ne pas concevoir la journalisation production autour de `print`; utiliser `sm.log`.

### GameClass

La doc qualifie GameClass de première classe/script de jeu exécutée et d'instance unique. **Nuance locale** : notre instrumentation top-level a vu plusieurs fichiers chargés avant le point de bootstrap injecté au début de `SurvivalGame.lua`. La formulation officielle décrit le lifecycle de GameClass, pas nécessairement l'ordre de toutes les évaluations `dofile`/dépendances. La preuve runtime locale prévaut pour notre hook placement.

### Network

`sendToServer`, `sendToClient(s)` et `setClientData` sont les primitives officielles. L'API avertit du coût réseau et recommande d'envoyer seulement lorsque nécessaire et aussi peu que possible. Cela confirme le design sparse-network.

### Storage

`sm.storage` est serveur-only ; l'écriture immédiate dans la DB du monde est décrite comme lente. Le design SMML doit donc bufferiser en mémoire et sauvegarder aux transitions. Le namespace « current mod » doit être traité avec prudence dans le direct-Survival : tous les mods SMML passent par la plateforme et doivent disposer en plus d'un namespace logique interne.

### Userdata lifetime

La documentation explique qu'une référence userdata est valide tant que l'objet existe. Notre v0.1.4 a démontré l'échec concret d'un Container conservé après invalidation. Le runtime doit vérifier `sm.exists`/réacquérir les handles plutôt que supposer leur permanence.

## Version du jeu / sauvegardes

Les annonces Steam indiquent que 1.0.6 est live en septembre 2026 et qu'une révision initiale a eu des problèmes de saves, avec restauration depuis `Backup`. Cela renforce le `UserDataVault` et la nécessité d'une stratégie de rollback hors jeu.

SteamDB expose les patterns UFS `.../Save`, `.../Save/Survival`, `.../Save/Survival/Backup`; PCGamingWiki cartographie Proton vers `steamapps/compatdata/387990/pfx/...`. Les chemins exacts restent à découvrir dynamiquement : ne pas graver un chemin utilisateur dans le produit.

## Frameworks Scrap Mechanic comparables

### community-owned-workshop/scrap-mechanic-bootstrapper

C'est le comparateur le plus proche du Content Composer : baseline versionnée, découverte de mods déclaratifs, restauration des merge targets, composition, conflits UUID/ressources, atlas central, suppression ciblée de `core_data.cbo`. Convergence forte avec SMML. Différences SMML : transactions/state/ownership plus larges, Linux/Proton explicite, profils/resolver/API runtime, et exigence de ne pas modifier les Steam Launch Options.

### Scrap Mechanic Mod Manager (Nexus)

Framework direct Survival récent, avec backups et menu in-game. Son changelog 1.4.6 décrit un bug critique : un script terrain était patché pour un mod absent, ce qui faisait disparaître les structures jusqu'au correctif. Leçon directe : une contribution conditionnelle ne doit jamais laisser une référence manquante ; validation avant commit + composition atomique + fail-closed.

### ScrapLab

Approche backup-first, exact-code guards et détection de mise à jour. ScrapLab accepte des opérations directes sur saves dans certaines fonctions, ce que SMML interdit, mais ses pratiques de sécurité/diagnostic sont pertinentes.

### Rivet / CarbonLauncher

Prouvent l'existence d'un axe natif DLL/hook. À suivre pour l'écosystème/interoperabilité, mais pas à adopter comme socle v1 avant que le backend Lua/data soit stabilisé.

## Analogues hors Scrap Mechanic

### BepInEx

Les métadonnées plugin (ID stable, SemVer, dépendances hard/soft, ranges) sont un bon modèle conceptuel pour le Resolver SMML. Ne pas copier les attributs C# ; transposer les invariants dans `smml.mod.json`.

### OSTree

L'idée d'arbres immuables content-addressed, déploiements reconstructifs et 3-way merge donne une direction solide au BaselineVault/StateManager. SMML ne doit pas devenir OSTree : seulement reprendre les propriétés utiles (immutabilité, provenance, rollback/reconstruction).

## Synthèse de recherche

La voie la plus robuste n'est ni « chaque mod a son installer », ni « injecter immédiatement une DLL » : c'est un **gestionnaire transactionnel + composition déclarative + runtime minimal abstrait**. L'écosystème 2026 confirme que la pression vers un framework commun existe déjà ; SMML doit se différencier par la sécurité d'état, la provenance et la stabilité contractuelle plutôt que par le nombre de hooks.
