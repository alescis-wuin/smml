# État courant

## Cible moteur validée

- Scrap Mechanic : `1.0.6`
- engine build : `889`
- Steam AppID : `387990`
- Steam build : `25442087`
- branche : `public`
- environnement principal validé : Linux + Steam + Proton, build Windows du jeu
- mode : Survival direct

**GP0 est fermé pour cette cible.**

## GP1 Foundation

Les sept contrats fondamentaux ont été spécifiés avec JSON Schema, fixtures et tests :

1. `GameTargetIdentity v1`
2. `TransactionJournal v1`
3. `PackageManifest v1`
4. `ContractDescriptor v1`
5. `HookPackManifest v1`
6. `Profile v1`
7. `Lockfile v1`

Le snapshot importé correspond au package historique `smml-gp1-foundation-v0.6.0`. Les sources sont désormais éclatées dans `specs/`, `schemas/`, `policies/`, `examples/` et `tests/` et doivent être versionnées directement par Git.

## Architecture retenue

```text
Manager / CLI / profils
        ↓
Resolver
        ↓
Transaction + State Manager
        ↓
Hook Patcher + Content Composer
        ↓
Runtime Adapter/Core
 ├─ TransportService
 └─ StorageService
        ↓
API SMML stable
        ↓
SDK optionnel
```

Le DLL/VFS natif reste différé. Le MVP reste Lua/data hybride.

## PathPolicy v1

`PathPolicy v1` est au stade **candidate freeze**. Il fixe une représentation portable des chemins logiques, Unicode NFC, une clé de collision normative Unicode 15.1.0, les restrictions Windows portables, les limites UTF-8 et les invariants no-follow pour symlink/reparse/hardlink. L'implémentation Python de référence accepte UCD 15.0.0 et 15.1.0 après vérification explicite de compatibilité, ce qui couvre CPython 3.12 et 3.13 sans modifier la sémantique normative.

Les validateurs sémantiques existants (`GameTargetIdentity`, `TransactionJournal`, `PackageManifest`, `HookPackManifest`) utilisent désormais le même validateur de chemin de référence.

## Hashing v1

`Hashing v1` est au stade **candidate freeze**. Il centralise `sha256` sur octets exacts et `smml.content-tree-sha256/1`, rejette les chemins dupliqués/collisions portables, formalise les fingerprints exact, canonique, sous-arbre et `ManagedOutputSet`, et fournit des vecteurs de conformité exécutables.

Les digests de Profile/manifest/package utilisent désormais la même primitive de référence au lieu d'implémentations ad hoc.

## GameTargetInspector v1.1 / canonical policy v2

`GameTargetInspector` vérifie le Steam appmanifest, refuse les builds inconnus, inventorie l'installation avec acquisition stable et seconde passe metadata, puis produit un `GameTargetIdentity` à partir des primitives PathPolicy/Hashing communes.

La sortie optionnelle `smml.file-inventory/1` permet désormais une comparaison fichier par fichier avec la baseline GP0. Le dépôt conserve une baseline B0 sanitizée/compressée de 61 370 records.

`smml.canonical-game-policy/2` est la politique active :

```text
Cache/ -> rebuildable-cache
Logs/  -> runtime-ephemeral
```

Le fingerprint canonique B0/B1 v2 est `f8356e5f0b660320bdcd196bc553114d688aeff43f20872438cbac1e1bc9668c` (41 251 fichiers). `Cache/Bundle/core_data.cbo` reste une target stricte malgré l'exclusion de `Cache/` du canonique.

Le plan courant connaît explicitement la cible Steam build `25442087` / branche `public`, le fingerprint canonique v2 connu et ne tente aucune reconnaissance heuristique d'une build inconnue.

## TransactionJournal runtime integration v1

L'intégration runtime read-only est au stade **candidate freeze**. Elle observe chaque chemin d'opération sans suivre les liens, calcule le SHA-256 exact des fichiers réguliers, classe l'état réel en `BEFORE | AFTER | FOREIGN` et produit `smml.transaction-recovery-report/1`.

Le rapport lie le journal à un `GameTargetIdentity` frais par build + fingerprint canonique v2 + target fingerprints stricts. Il ignore volontairement l'`installationExactFingerprint` et les `rootFingerprints`, qui peuvent dériver à cause du cache déjà classifié.

Le CLI de recovery n'écrit ni dans le game root ni dans le journal ; `RESUME_COMMIT` / `ROLLBACK_REQUIRED` sont uniquement des diagnostics. Symlink, reparse point, hardlink mutable, case mismatch et topologie de chemin invalide bloquent fail-closed.

## TransactionEngine v1 — non-destructive core

La première tranche du `TransactionEngine` est au stade **candidate freeze** sans mutation du game root. Elle introduit :

- `StagingStore` transaction-local adressé par SHA-256 ;
- `smml.transaction-staging-manifest/1` ;
- capture des bytes `before` nécessaires au rollback ;
- import des bytes `after` nécessaires au futur commit ;
- `JournalStore` whole-file avec `fsync` + remplacement atomique sur la référence POSIX ;
- ordre durable `PLANNED -> staging blobs -> staging manifest -> PREPARED` ;
- reprise idempotente après interruption ;
- fault injection autour des publications persistantes non destructives.

Le CLI `transaction-preparer` écrit uniquement dans un `stateRoot` distinct du jeu. `PREPARED` signifie désormais que les bytes nécessaires au commit et au rollback sont effectivement recoverables depuis le staging vérifié.

## Prochaine priorité

Avant d'activer toute mutation réelle du jeu :

```text
inter-process transaction lock
        ↓
TransactionEngine commit / verify / rollback
        ↓
fault injection destructive sur game roots synthétiques
```

La preuve de durabilité Windows reste ouverte ; l'environnement GP1 actuellement validé est Linux/Proton. Ensuite : `PackageValidator`, `Resolver`, Content Composer MVP et vertical slice Pallet64.
