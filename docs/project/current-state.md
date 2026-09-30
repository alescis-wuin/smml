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

## Prochaine priorité

Le prochain chantier P0 est le cœur de sûreté :

```text
PathPolicy
Hashing
GameTargetInspector
TransactionJournal
TransactionEngine
```

Le `TransactionEngine` doit être développé avec fault injection et recovery fail-closed avant toute GUI.

Ensuite : `PackageValidator`, `Resolver`, puis Content Composer MVP et vertical slice Pallet64.
