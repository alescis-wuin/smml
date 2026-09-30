# SMML GP1 Foundation v0.6.0 — snapshot importé

Ce package contient les sept contrats fondamentaux prévus en tête de GP1 Foundation :

1. `GameTargetIdentity v1` — candidate freeze depuis v0.1.1 ;
2. `TransactionJournal v1` — candidate freeze depuis v0.2.0 ;
3. `PackageManifest v1` — candidate freeze depuis v0.3.0 ;
4. `ContractDescriptor v1` — candidate freeze depuis v0.4.0 ;
5. `HookPackManifest v1` — candidate freeze depuis v0.5.0 ;
6. `Profile v1` — première version candidate ;
7. `Lockfile v1` — première version candidate.

## Profile v1

Fichiers principaux :

- `specs/profile.md` ;
- `schemas/smml.profile-1.schema.json` ;
- `examples/profile.valid.full-example.json` ;
- `examples/profile.valid.minimal.json` ;
- fixtures invalides `profile.invalid.*.json` ;
- `tests/profile_validation.py` ;
- `tests/test_profile.py` ;
- `tests/profile_vectors.json`.

Principes :

- le Profile représente l'intention portable, pas la résolution ;
- cible par contraintes stables (`steamAppId`, build/version/branch/fingerprint canonique optionnels) ;
- packages racines par `id + range` ;
- dépendances soft pilotées explicitement ;
- ambiguïté de provider exclusive = erreur en v1 ;
- sélections de providers possibles sans rendre le provider package racine ;
- aucun chemin local, package digest, ordre résolu, timestamp ou état d'installation.

## Lockfile v1

Fichiers principaux :

- `specs/lockfile.md` ;
- `schemas/smml.lockfile-1.schema.json` ;
- `examples/lockfile.valid.full-example.json` ;
- `examples/lockfile.valid.resolved-only.json` ;
- fixtures invalides `lockfile.invalid.*.json` ;
- `tests/lockfile_validation.py` ;
- `tests/test_lockfile.py` ;
- `tests/lockfile_vectors.json`.

Principes :

- provenance du Profile par ID + SHA-256 des octets exacts ;
- cible résolue stable sans `installationExactFingerprint` ;
- packages exacts par `id + version + packageDigest + manifestDigest` ;
- liste d'artefacts exacts avec SHA-256 ;
- composants `hookPack`, `api`, `sdk` explicitement verrouillés ;
- roots du Profile séparés des packages transitifs/de plateforme ;
- ordre final unique dans `loadOrder` ;
- providers de capabilities verrouillés ;
- edges explicables et orientés `from -> to = doit précéder` ;
- cohérence des edges vérifiée contre `loadOrder`, ranges et manifests ;
- aucune donnée volatile (timestamp, chemin local, transaction ID) ;
- `finalContentFingerprint` optionnel pendant GP1, basé sur le futur `ManagedOutputSet` staged.

## Exemple de cible GP0

Les fixtures utilisent la cible de référence établie par GP0 :

```text
Steam AppID       387990
gameVersion       1.0.6
engineBuild       889
Steam build       25442087
branch            public
canonical fp      6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964
```

Les IDs `com.example.*` / `org.smml.*` de démonstration ne prétendent pas définir les futurs IDs de production.

## Validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/validate_examples.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests/test_game_target_identity.py \
  tests/test_transaction_journal.py \
  tests/test_package_manifest.py \
  tests/test_contract_descriptor.py \
  tests/test_hook_pack_manifest.py \
  tests/test_profile.py \
  tests/test_lockfile.py
```

Dépendance de test : `jsonschema >= 4`.

Résultat attendu pour v0.6.0 :

```text
94 / 94 example fixtures PASS
127 / 127 unit tests PASS
```

## Packaging

Les artefacts temporaires Python (`__pycache__`, `*.pyc`) ne font pas partie du package et ne doivent jamais entrer dans `SHA256SUMS`.
