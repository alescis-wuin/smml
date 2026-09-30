# Changelog

## 0.6.0 — 2026-09-29

- Ajout de `Profile` v1 et du schéma `smml.profile/1`.
- Séparation normative entre intention portable (`Profile`) et résolution exacte (`Lockfile`).
- Ajout d'une cible Profile portable sans fingerprint exact d'installation ni chemins locaux.
- Ajout des packages racines avec ranges SemVer SMML v1.
- Ajout des politiques `softDependencies`, `providerAmbiguity` et sélections explicites de providers de capabilities.
- Ajout de `Lockfile` v1 et du schéma `smml.lockfile/1`.
- Verrouillage des packages exacts via `id + version + packageDigest + manifestDigest`.
- Ajout d'une projection stable de la cible : build/branch/platform + fingerprint canonique, sans artefacts runtime exacts.
- Ajout des artefacts sélectionnés, composants `hookPack`/`api`/`sdk`, roots, ordre final et providers de capabilities.
- Ajout d'edges explicables `hardDependency`, `softDependency`, `capability`, `loadBefore`, `loadAfter` avec orientation canonique `from -> to = doit précéder`.
- Validation que chaque edge respecte `loadOrder` et que les versions verrouillées satisfont les ranges de dépendance.
- Ajout d'une validation croisée Profile -> Lockfile et Lockfile -> PackageManifest.
- Interdiction des timestamps/chemins locaux/IDs aléatoires dans le Lockfile.
- Réservation de `finalContentFingerprint` pour le `ManagedOutputSet`, optionnelle pendant GP1 et obligatoire pour un futur lockfile finalisé/appliqué.
- Rôle API/SDK enregistré mais preuve sémantique différée jusqu'à standardisation d'un rôle/capability canonique dans les manifests.

## 0.5.0 — 2026-09-29

- Ajout de `HookPackManifest` v1 et du schéma `smml.hook-pack-manifest/1`.
- Sélection de cible renforcée : métadonnées exactes + fingerprint canonique + preconditions des fichiers baseline + anchors.
- Ajout de `targetFiles` avec listes explicites de hashes baseline supportés.
- Ajout des anchors `exact-text` et `lua-function`, toujours `exactly-one`.
- Ajout des transformations déclaratives `insert-before`, `insert-after`, `replace-region`, `wrap-prefix`, `wrap-postfix` et `conditional-short-circuit`.
- Ajout d'un ordre déterministe global des hooks et local des transformations via `sequence`.
- Ajout des références aux Runtime Adapters, ContractDescriptors et fragments de patch typés dans `PackageManifest`.
- Ajout de marqueurs begin/end uniques pour vérification/idempotence.
- Ajout de conséquences de cache limitées à `invalidate-file` sur chemin exact.
- Formalisation de la frontière staging -> TransactionJournal -> TransactionEngine.
- Allocation `setClientData` conservée hors v1 car encore ouverte dans le handoff.
- Ajout de 10 fixtures HookPackManifest, de vecteurs machine-readable et de tests de cohérence croisée.
- Correction de la documentation de package qui n'avait pas été actualisée en v0.4.0.

## 0.4.0 — 2026-09-29

- Ajout de `ContractDescriptor` v1 et du schéma `smml.contract-descriptor/1`.
- Ajout des catégories `notification`, `cancellable`, `transform`, `query` et `service`.
- Ajout des politiques de combinaison et d'erreur spécifiques par catégorie.
- Cancellable v1 limité au serveur autoritaire.
- Transform v1 endomorphe et pipeline déterministe.
- Références de schémas package-locales avec builtin `smml.decision/1`.
- Ajout de tests de registre, versions exactes, combinaison cancellable et cohérence avec `PackageManifest`.

## 0.3.0 — 2026-09-29

- Ajout de `PackageManifest` v1.
- Ajout du schéma `smml.package-manifest/1`.
- Ajout d'un ID package permanent lower-case de type namespace/reverse-DNS.
- Ajout de SemVer 2.0.0 stricte pour les packages.
- Ajout d'une grammaire SMML v1 explicite pour les ranges de dépendances/conflits.
- Ajout des target selectors exacts compatibles avec `GameTargetIdentity`.
- Ajout des dépendances `hard` / `soft`.
- Ajout des capabilities provided/required avec cardinalité explicite.
- Ajout des conflits packages/capabilities.
- Ajout des contraintes `loadBefore` / `loadAfter`.
- Ajout de `PersistenceImpact = none | runtimeState | playerState | worldContent`.
- Ajout des entrypoints optionnels `shared` / `server` / `client`.
- Ajout de références d'artefacts extensibles par `id + type + path`.
- Ajout de l'inventaire de fichiers `path + size + sha256`.
- Définition de `manifestDigest` et `packageDigest` comme valeurs dérivées hors manifest afin d'éviter les hashes auto-référents.
- Ajout de fixtures valides/invalides et de tests SemVer, ranges, target matching, inventaire et identité cryptographique.

## 0.2.0 — 2026-09-29

- Ajout de `TransactionJournal` v1.
- Ajout du schéma `smml.transaction-journal/1`.
- Ajout des phases nominales et d'incident définies par le handoff GP1.
- Ajout du modèle de mutation `create` / `replace` / `delete` avec états avant/après.
- Ajout de `journalRevision`, `phaseHistory` et `incidents` pour recovery/audit.
- Ajout du recovery classifier `BEFORE` / `AFTER` / `FOREIGN`.
- Ajout de fixtures de crash avec statut de journal volontairement en retard sur l'état observé.
- Ajout des invariants de séquence, collisions de chemins, transitions de phase et cohérence phase/statut.
- Maintien explicite des mutations de répertoires et primitives OS de durabilité hors du scope du journal v1.

## 0.1.1 — 2026-09-29

- Revue critique pré-freeze de `GameTargetIdentity` v1.
- Distinction explicite entre hash d'arbre (`smml.content-tree-sha256/1`) et hash de fichier (`sha256`).
- Ajout du JSON Schema de `smml.canonical-game-policy/1`.
- `$id` des schémas déplacés vers des URN SMML stables.
- Sémantique de case folding figée sur Unicode 15.1.0 dans la spécification.
- Ajout de tests de conformité pour la politique et les tags d'algorithme.

## 0.1.0 — 2026-09-29

- Ajout de `GameTargetIdentity` v1.
- Ajout de `smml.content-tree-sha256/1` comme algorithme de fingerprint d'arbre.
- Ajout de `smml.canonical-game-policy/1`, limitée à `Logs/`.
- Ajout de la fixture Scrap Mechanic 1.0.6 / engine 889 / Steam build 25442087.
- Ajout des tests JSON Schema et invariants sémantiques.
