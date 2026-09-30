# Organisation du dépôt SMML

## Objectifs

L'organisation du dépôt suit quatre règles :

1. une seule copie canonique d'un contenu actif ;
2. Git porte l'historique, pas les suffixes de version dans les chemins ;
3. les artefacts générés/lourds restent hors du dépôt ;
4. les preuves nécessaires aux décisions restent compactes, reproductibles et sanitizées.

## Convention de nommage

### Répertoires et documentation

Utiliser `kebab-case` ASCII :

```text
docs/project/current-state.md
tools/gp0/network-storage-probe/
specs/transaction-journal.md
```

Exceptions admises pour les fichiers conventionnels : `README.md`, `CHANGELOG.md`, `Makefile`.

### Python

Utiliser `snake_case.py` :

```text
smml_gp0_scan.py
check_repository.py
```

### Schémas et formats publics

Les noms existants sont conservés car ils correspondent aux identifiants de formats versionnés :

```text
schemas/smml.profile-1.schema.json
schemas/smml.lockfile-1.schema.json
```

Le numéro représente la version du **format**, pas une version de fichier à gérer manuellement.

## Source canonique

| Contenu | Emplacement |
|---|---|
| spécifications | `specs/` |
| JSON Schemas | `schemas/` |
| politiques versionnées | `policies/` |
| exemples de contrats | `examples/` |
| tests de conformité | `tests/` |
| implémentations de référence | `reference/python/` |
| outils GP1 | `tools/gp1/` |
| architecture / état | `docs/` |
| preuves compactes | `evidence/` |
| outils GP0 | `tools/gp0/` |
| artefacts lourds locaux | `artifacts/` |

## Versionnement

Ne pas créer :

```text
foo-v1.py
foo-v2.py
foo-final.py
foo-final-2.py
```

Modifier `foo.py`, committer, puis créer un tag si la version doit être référencée durablement.

Les formats publics restent explicitement versionnés dans leur contenu et leur identifiant (`smml.package-manifest/1`, etc.).

## Artefacts et preuves

Les ZIP de release et handoffs ne sont pas une source canonique. Ils sont construits à partir du dépôt et vont dans `dist/` ou `artifacts/`.

Les preuves brutes susceptibles de contenir des chemins locaux, SteamID, noms de joueurs ou logs volumineux ne doivent pas être commitées. Conserver une synthèse sanitizée et les digests nécessaires à la traçabilité.

## Branches et commits

Branche principale : `main`.

Préférer des commits atomiques, par exemple :

```text
spec: add PathPolicy v1
feat: implement GameTargetInspector
fix: reject case-insensitive package path collision
test: add crash-after-first-mutation recovery case
docs: update GP1 current state
```

Tags recommandés pour les jalons :

```text
gp1-foundation-v0.6.0
smml-v0.1.0
```
