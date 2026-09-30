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

## GameTargetInspector v1

`GameTargetInspector v1` est au stade **candidate freeze**. Il vérifie le Steam appmanifest, refuse les builds inconnus, inventorie l'installation avec acquisition stable et seconde passe metadata, puis produit un `GameTargetIdentity` à partir des primitives PathPolicy/Hashing communes.

Le plan courant connaît explicitement la cible Steam build `25442087` / branche `public` et ne tente aucune reconnaissance heuristique d'une build inconnue.

## Prochaine priorité

Le prochain chantier P0 du cœur de sûreté est :

```text
TransactionJournal integration
TransactionEngine
```

Le `TransactionEngine` doit être développé avec fault injection et recovery fail-closed avant toute GUI.

Ensuite : `PackageValidator`, `Resolver`, puis Content Composer MVP et vertical slice Pallet64.
