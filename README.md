# SMML — Scrap Mechanic Mod Loader / Manager

SMML est un projet de plateforme de modding pour **Scrap Mechanic Survival** orienté vers la composition déterministe, les transactions récupérables, la provenance, les profils/lockfiles et une API runtime stable.

## État du projet

- **GP0 — Ground Proof : fermé** pour Scrap Mechanic `1.0.6`, engine build `889`, Steam build `25442087`, AppID `387990`.
- **GP1 — Foundation : en cours**.
- Les sept contrats fondamentaux sont au stade **candidate freeze** :
  `GameTargetIdentity`, `TransactionJournal`, `PackageManifest`, `ContractDescriptor`, `HookPackManifest`, `Profile`, `Lockfile`.
- `PathPolicy v1` est au stade **candidate freeze** avec politique versionnée et tests exécutables.
- `Hashing v1` est au stade **candidate freeze** : SHA-256 d'octets exacts, `smml.content-tree-sha256/1`, fingerprints exact/canonique/sous-arbre/ManagedOutputSet et vecteurs normatifs.
- Prochaine priorité : `GameTargetInspector`, puis intégration `TransactionJournal` et `TransactionEngine` avec fault injection avant toute GUI.

La source de vérité active est le dépôt Git. Les anciennes archives versionnées manuellement ne doivent plus être utilisées comme source canonique.

## Arborescence

```text
.
├── specs/                  Spécifications normatives GP1
├── schemas/                JSON Schemas versionnés
├── policies/               Politiques sérialisées versionnées
├── examples/               Fixtures valides/invalides
├── tests/                  Tests de conformité des contrats
├── tools/
│   ├── gp0/                Outils/probes GP0 conservés comme références
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

Dépendances de test :

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

Puis :

```bash
make test
make check
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
