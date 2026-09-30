# SMML — Scrap Mechanic Mod Loader / Manager

SMML est un projet de plateforme de modding pour **Scrap Mechanic Survival** orienté vers la composition déterministe, les transactions récupérables, la provenance, les profils/lockfiles et une API runtime stable.

## État du projet

- **GP0 — Ground Proof : fermé** pour Scrap Mechanic `1.0.6`, engine build `889`, Steam build `25442087`, AppID `387990`.
- **GP1 — Foundation : en cours**.
- Les sept contrats fondamentaux sont au stade **candidate freeze** :
  `GameTargetIdentity`, `TransactionJournal`, `PackageManifest`, `ContractDescriptor`, `HookPackManifest`, `Profile`, `Lockfile`.
- `PathPolicy v1` est au stade **candidate freeze** avec politique versionnée et tests exécutables.
- `Hashing v1` est au stade **candidate freeze** : SHA-256 d'octets exacts, `smml.content-tree-sha256/1`, fingerprints exact/canonique/sous-arbre/ManagedOutputSet et vecteurs normatifs.
- `GameTargetInspector v1.1` ajoute une sortie d’inventaire déterministe, un diff `Cache/` contre la baseline GP0 et la vérification d’un fingerprint canonique connu.
- `smml.canonical-game-policy/2` est la politique active : `Cache/` est classé rebuildable-cache et `Logs/` runtime-ephemeral, tandis que les target fingerprints restent stricts.
- Prochaine priorité : intégration `TransactionJournal`, puis `TransactionEngine` avec fault injection avant toute GUI.

La source de vérité active est le dépôt Git. Les anciennes archives versionnées manuellement ne doivent plus être utilisées comme source canonique.

## Arborescence

```text
.
├── specs/                  Spécifications normatives GP1
├── schemas/                JSON Schemas versionnés
├── policies/               Politiques sérialisées versionnées
├── examples/               Fixtures valides/invalides
├── tests/                  Tests de conformité des contrats
├── reference/python/       Implémentations Python de référence des specs
├── tools/
│   ├── gp0/                Outils/probes GP0 conservés comme références
│   ├── gp1/                Outils exécutables GP1
│   └── repo/               Contrôles d'hygiène du dépôt
├── docs/
│   ├── project/            État, décisions, roadmap, conventions
│   ├── architecture/       Architecture de référence
│   ├── gp0/                Résultats et spécifications GP0
│   ├── research/           Recherche externe historique
│   ├── reviews/            Audits/revues
│   ├── reports/            Rapports historiques
│   └── foundation/         Historique du package GP1 Foundation
├── evidence/               Preuves compactes et sanitizées
└── artifacts/              Artefacts locaux lourds/non suivis par Git
```

Voir [`docs/project/repository-layout.md`](docs/project/repository-layout.md) pour les conventions détaillées.

## Validation GP1

L'implémentation Python de référence supporte actuellement **CPython 3.12 et 3.13**. `PathPolicy v1` conserve Unicode 15.1.0 comme sémantique normative, avec une compatibilité vérifiée pour les runtimes UCD 15.0.0 (Python 3.12) et 15.1.0 (Python 3.13). Les runtimes Unicode plus récents sont refusés en v1 tant que les tables normatives ne sont pas embarquées indépendamment du runtime.

Installation recommandée :

```bash
python3 -m venv .venv
. .venv/bin/activate
make setup
make check
```

Inspection réelle recommandée :

```bash
python tools/gp1/game-target-inspector/smml_game_target_inspector.py \
  "$HOME/.local/share/Steam/steamapps/common/Scrap Mechanic" \
  --compatibility-layer proton \
  --output artifacts/game-target.json \
  --inventory-output artifacts/game-target-inventory.json.gz \
  --cache-diff-output artifacts/cache-diff.json \
  --require-known-canonical
```

Équivalent sans `make` :

```bash
python3 -m pip install -r requirements-dev.txt
python3 tests/validate_examples.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/repo/check_repository.py
```

Les commandes équivalentes sans `make` sont documentées dans `docs/foundation/foundation-v0.6.0.md`.

## Politique Git

- Une source active ne porte pas sa version dans son nom de fichier ou de dossier ; Git porte son historique.
- Les versions de **formats publics** restent explicites dans leurs identifiants (`smml.profile/1`, etc.).
- Les ZIP de release, scans complets, caches, résultats temporaires et états locaux vont dans `artifacts/` ou `dist/` et ne sont pas commités.
- Les preuves nécessaires à une décision architecturale sont conservées sous forme compacte et sanitizée dans `evidence/`.
- Les changements structurants doivent mettre à jour `docs/project/current-state.md`, `docs/project/roadmap.md` et, si nécessaire, `docs/project/decisions-and-invariants.md`.

## Historique importé

Le dépôt a été initialisé à partir de l'ancien répertoire sans Git. Les fichiers écartés, déplacés ou remplacés sont inventoriés avec leur SHA-256 dans [`docs/project/import-manifest.csv`](docs/project/import-manifest.csv).

L'archive d'origine reste la référence pour les artefacts historiques non importés dans Git.

## Licence

Aucune licence de redistribution n'est définie dans les sources importées. Ne pas en déduire une implicitement.
