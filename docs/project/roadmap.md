# Roadmap active

## P0 — Transaction foundation

1. ✅ `PathPolicy v1` — candidate freeze
2. hashing déterministe
3. `GameTargetInspector`
4. intégration de `TransactionJournal v1`
5. `TransactionEngine`
6. verrou inter-processus
7. durabilité adaptée à l'OS (`fsync`, atomic replace, etc.)
8. fault injection et recovery

Scénarios minimaux : crash avant commit, après opération 1, après opération N, avant vérification, après mutation avant acquittement du journal, modification étrangère entre deux phases.

## P1 — Package Validator

- zip-slip / chemins absolus ;
- symlink / hardlink / reparse points ;
- collisions case-insensitive ;
- noms réservés ;
- chemins normalisés en double ;
- limites nombre/taille/ratio ;
- `packageDigest`, `manifestDigest`, `fileDigests`.

## P1 — Resolver

- SemVer ;
- hard/soft dependencies ;
- capabilities et cardinalité ;
- conflicts ;
- `loadBefore` / `loadAfter` ;
- ordre déterministe ;
- provenance des edges et explication.

## P1 — Content Composer MVP

Première vague : assets, shapes, recipes, localisation, IconMap.

## P2 — Vertical slice

Pallet64 en premier, puis Composteur, puis Presse à palettes.
