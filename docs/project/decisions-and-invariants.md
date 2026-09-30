# Décisions et invariants

## Invariants non négociables

1. Survival direct, pas Custom Game.
2. Sauvegardes : aucune édition directe ; snapshot récursif de `Save/` avant mutation expérimentale ou installation susceptible d'altérer le monde.
3. Serveur autoritaire pour inventaire, production, persistance et validation critique.
4. UUID publiés considérés stables ; migration explicite si changement inévitable.
5. Pas de `sudo`, pas de téléchargement réseau au runtime installateur, pas de modification automatique des Steam Launch Options.
6. Cache : invalidation ciblée et prouvée ; jamais purge globale réflexe.
7. Fichiers vanilla partagés : composition/reconstruction depuis baseline + contributions, pas chaîne de patchs indépendants.
8. Avant écriture : préflight hashes + drift ; après écriture : vérification hashes ; rollback exact.
9. Ne supprimer qu'un fichier possédé dont le hash actuel est celui attendu ; sinon préserver et bloquer.
10. Hook fragile côté jeu, API stable côté mods : les mods ne connaissent pas `CarryTool.lua`, `SurvivalGame.lua`, etc.
11. Hook Patcher Engine indépendant des Hook Definition Packs versionnés par build.
12. Content Composer sémantique, avec provenance par élément et explication de conflit.
13. Runtime réseau et stockage parcimonieux.
14. Preuve : moteur > local > officiel > statique > communauté > inférence.
15. Une capability observée sur une build n'est pas une garantie universelle ; la build/fingerprint décide.

## Décisions architecturales établies

- Runtime global chargé via un `ensureRuntime()` multi-entry idempotent.
- Pas de dépendance à `rawget/rawset/debug.traceback` sur la build testée.
- `xpcall` est la frontière d'isolation des handlers ; les diagnostics ajoutent `modId`, `contractId`, phase, callback, build et session.
- `sm.exists` / reacquisition avant réutilisation de userdata dont la durée de vie n'est pas garantie.
- Contrats API versionnés individuellement ; catégories : Notification, Cancellable, Transform, Query, Service.
- Resolver distinct du Manager ; support dépendances dures/molles, contraintes de versions, capabilities, conflits, ordre déterministe et lockfile.
- State model : installation officielle attendue → baseline locale → état géré SMML → état runtime.
- Désinstallation reconstructive : recalculer l'état désiré avec les mods restants, jamais appliquer des « inverse patches » fragiles.
- Baseline Vault immuable ; optimisation CAS/dédup possible plus tard.
- `PathPolicy v1` : chemins logiques UTF-8/NFC, séparateur `/`, pas de normalisation silencieuse, collisions détectées avec Unicode Default Case Folding 15.1.0.
- Les noms/caractères incompatibles avec la politique portable Windows sont rejetés même sur un host POSIX.
- Les cibles gérées ne suivent jamais symlink/reparse point ; une mutation d'un fichier hardlinké est refusée en v1.
- `sha256` signifie toujours SHA-256 des octets exacts, sans normalisation texte/JSON implicite.
- `smml.content-tree-sha256/1` hash des records `path + NUL + size + NUL + sha256 + LF`, triés avec `PortableCollisionKey`; doublons et collisions portables sont refusés.
- Les fingerprints exact, canonique, sous-arbre et `ManagedOutputSet` partagent l'algorithme d'arbre mais leur rôle/contexte reste distinct ; v1 n'ajoute pas de domain separation afin de préserver GP0.
- `GameTargetInspector v1.1` obtient AppID/build/branche depuis le Steam appmanifest local et traduit `gameVersion`/`engineBuild` uniquement via un plan versionné ; une build inconnue est fail-closed.
- `smml.canonical-game-policy/2` exclut `Cache/` (rebuildable-cache) et `Logs/` (runtime-ephemeral) du fingerprint canonique. Cette exclusion est une règle d'identité, pas une autorisation de purge.
- Les fichiers exclus du canonique peuvent rester des preuves fortes : `Cache/Bundle/core_data.cbo` conserve un target fingerprint SHA-256 strict.
- Le `GameTargetInspector` peut produire `smml.file-inventory/1`; la comparaison de baseline utilise l'inventaire B0 sanitizé et ne dépend pas de chemins locaux.
- L'inspection exige un inventaire stable en deux passes et ne constitue jamais une autorisation de mutation ; le TransactionEngine revalide les préconditions.
- `TransactionJournal runtime integration v1` observe le filesystem sans mutation et considère les octets observés comme autorité pour `BEFORE | AFTER | FOREIGN`; le `status` du journal reste une connaissance durable potentiellement en retard.
- Le recovery runtime lie la cible sur build + fingerprint canonique + target fingerprints stricts ; l'exact fingerprint et les root fingerprints ne bloquent pas à eux seuls le recovery à cause du drift `Cache/` prouvé.
- Un diagnostic `RESUME_COMMIT` ou `ROLLBACK_REQUIRED` n'autorise aucune écriture ; seul le futur TransactionEngine pourra matérialiser l'action après revalidation et write-ahead durable.
- Le recovery inspector refuse toute sortie sous le game root et bloque fail-closed sur symlink, reparse point, hardlink mutable, case mismatch ou ancêtre invalide.
- `smml explain <path>` doit exposer provenance/ownership/conflits.

## Décisions réseau/persistance gelées après GP0.5

- `SurvivalGame.network` est le backend transport MVP derrière `TransportService`.
- La présence de ce backend n'est jamais exposée aux mods : un futur ScriptableObject/Rivet/native backend doit pouvoir le remplacer sans casser les contrats publics.
- RPC : validation stricte de l'enveloppe, du `contractId`, de la version et du payload avant dispatch.
- Toute erreur de handler est isolée par `xpcall`; le dispatcher continue.
- `sendToServer` / `sendToClient(s)` : commandes et événements ponctuels.
- `setClientData` : petit état serveur répliqué et utile aux clients tardifs.
- Canaux 3 et 4 sont utilisables sur la build 1.0.6.889 testée ; le choix d'un canal est une donnée de Hook Pack/capability, pas un numéro public stable.
- Le runtime client peut être détruit/recréé au leave/rejoin ; aucun service client ne dépend d'un état Lua durable.
- `sm.storage` est encapsulé par `StorageService`, server-side.
- Namespace logique SMML par `modId`, même si le moteur fournit sa propre notion de « current mod ».
- Données persistées avec `schemaVersion`; migrations déterministes/idempotentes.
- Écritures storage seulement aux transitions nécessaires, avec dirty/coalescing ; jamais à chaque tick.

## Décisions volontairement ouvertes pour GP1+

- Encodage physique final des clés/records `StorageService`.
- Politique exacte d'allocation des canaux `setClientData` entre Core/Hook Pack/capabilities.
- Handshake/fingerprints multijoueur et distinction mods client-only/server-only/both.
- Support futur d'un serveur dédié si Axolot fournit une distribution supportée.
- Validation réseau sur deux machines physiques/WAN : utile pour latence/perf, non bloquante pour la fermeture GP0 actuelle.
- VFS/native DLL/Rivet backend : option future, pas fondation v1.
