# Changelog

## Unreleased

### TransactionEngine v1 — non-destructive core — 2026-09-30

- ajout de `specs/transaction-engine.md` et `smml.transaction-staging-manifest/1` ;
- `StagingStore` transaction-local adressé par SHA-256 avec publication atomique, relecture et vérification des blobs ;
- capture durable des bytes `before` nécessaires au rollback et import des bytes `after` nécessaires au futur commit ;
- `JournalStore` avec réécriture whole-file, `fsync`, remplacement atomique et invariants de révision/immutabilité ;
- préparation `PLANNED -> PREPARED` uniquement après staging + manifest durables ;
- reprise idempotente d'une préparation interrompue et revalidation d'un état déjà `PREPARED` ;
- fault injection non destructive autour des blobs, manifests et publications du journal ;
- CLI `transaction-preparer` qui écrit uniquement sous un `stateRoot` hors du game root ;
- aucun commit/verify/rollback du jeu activé dans cette tranche.

### TransactionJournal runtime integration v1 — 2026-09-30

- ajout de `smml.transaction-recovery-report/1` et de `specs/transaction-journal-runtime.md` ;
- observation filesystem read-only des chemins de transaction avec hashing stable sans suivi de liens sur la référence POSIX ;
- classification physique `BEFORE | AFTER | FOREIGN` indépendante du `status` durable du journal ;
- liaison du journal à un `GameTargetIdentity` frais via build, fingerprint canonique v2 et target fingerprints stricts, sans exiger l'exact/root Cache ;
- décisions phase-aware : resume commit, ready-to-verify, recovery required, rollback diagnostics et états terminaux ;
- blocage fail-closed sur symlink, reparse point, hardlink mutable, case mismatch et ancêtre invalide ;
- CLI `transaction-recovery-inspector` qui refuse toute sortie dans le game root et n'écrit jamais le journal ;
- déplacement des validateurs `GameTargetIdentity` et `TransactionJournal` vers `reference/python/smml_reference/` avec shims de compatibilité pour les tests.

### GameTargetInspector v1.1 / canonical cache classification — 2026-09-30

- ajout de `smml.file-inventory/1` et `smml.file-inventory-diff/1` ;
- sortie optionnelle d'inventaire complet JSON/JSON.gz déterministe ;
- baseline GP0 B0 sanitizée de 61 370 records conservée comme preuve compacte ;
- diff automatique `Cache/` avec classification `rebuildable-cache` et marquage des targets strictes ;
- ajout de `smml.canonical-game-policy/2`, excluant explicitement `Cache/` et `Logs/` ;
- fingerprint canonique B0/B1 v2 : `f8356e5f0b660320bdcd196bc553114d688aeff43f20872438cbac1e1bc9668c` ;
- extension du plan d'inspection avec fingerprint canonique connu et roots/targets diagnostiques supplémentaires ;
- conservation de `Cache/Bundle/core_data.cbo` comme target SHA-256 stricte ;
- contrôle d'hygiène basé sur les fichiers suivis par Git afin que les `__pycache__` ignorés localement ne fassent plus échouer `make check`.

### PathPolicy / GameTargetInspector compatibility fix — 2026-09-30

- correction de l'incompatibilité de la référence Python avec CPython 3.12 / UCD 15.0.0 ;
- conservation de Unicode 15.1.0 comme sémantique normative de `PortableCollisionKey` ;
- compatibilité bornée UCD 15.0.0/15.1.0 avec auto-vérification des 627 caractères ajoutés en Unicode 15.1 et des sentinelles de full case folding ;
- rejet explicite des runtimes UCD plus récents tant que les tables normatives ne sont pas embarquées ;
- séparation `requirements.txt` (runtime) / `requirements-dev.txt` et ajout de `make setup` ;
- diagnostic CLI explicite quand `jsonschema` n'est pas installé.

### GameTargetInspector v1 — 2026-09-30

- ajout de `specs/game-target-inspector.md` et du plan `smml.game-target-inspection-plan/1` ;
- vérification de l'AppID, Steam build, branche et `installdir` depuis le appmanifest local ;
- mapping explicite Steam build -> gameVersion/engineBuild, sans reconnaissance heuristique des builds inconnues ;
- inventaire read-only fail-closed avec rejet symlink/reparse/objets spéciaux/collisions portables ;
- acquisition stable `lstat/fstat` avant/après hashing et seconde passe metadata ;
- production des fingerprints exact, canonique, roots et targets via `Hashing v1` ;
- déplacement des primitives PathPolicy/Hashing vers `reference/python/smml_reference/` pour supprimer la dépendance des outils à `tests/` ;
- ajout du rejet explicite des noms POSIX non encodables UTF-8 (`PATH_NOT_UTF8`) ;
- ajout du CLI GP1 et de tests de conformité de l'Inspector.

### Hashing v1 — 2026-09-30

- ajout de `specs/hashing.md` et de vecteurs normatifs exécutables ;
- formalisation de `sha256` sur octets exacts et de `smml.content-tree-sha256/1` ;
- distinction explicite des rôles exact/canonique/sous-arbre/ManagedOutputSet ;
- rejet des chemins dupliqués et des collisions `PortableCollisionKey` dans un arbre ;
- clarification des sous-arbres : chemins conservés relatifs au game root, compatible avec GP0 ;
- centralisation des digests Profile/manifest/package sur la primitive de référence ;
- filtrage canonique exact et sensible à la casse après validation PathPolicy ;
- ajout de tests de conformité et suppression du helper historique ambigu.

### PathPolicy v1 — 2026-09-30

- ajout de `specs/path-policy.md` et de la politique sérialisée `smml.path-policy/1` ;
- chemins logiques UTF-8/NFC avec séparateur `/` et absence de normalisation silencieuse ;
- détection de collisions via Unicode Default Case Folding 15.1.0 ;
- règles portables Windows : caractères/noms réservés, trailing dot/space, drive/namespace forms ;
- bornes v1 : 4096 octets UTF-8 par chemin, 255 par segment, 256 segments ;
- invariants filesystem no-follow : racine de confiance, symlink/reparse refusés, hardlinks mutables refusés ;
- centralisation des validations de chemin utilisées par les contrats GP1 existants ;
- ajout de vecteurs et tests de conformité PathPolicy.

### Repository bootstrap — 2026-09-30

- migration vers une arborescence Git canonique ;
- suppression des doublons actifs et des noms de sources versionnés manuellement ;
- import du snapshot GP1 Foundation v0.6.0 dans `specs/`, `schemas/`, `policies/`, `examples/` et `tests/` ;
- conservation des dernières sources GP0 utiles sous `tools/gp0/` ;
- séparation des preuves compactes (`evidence/`) et des artefacts lourds locaux (`artifacts/`) ;
- ajout de `README.md`, `.gitignore`, `.gitattributes`, `.editorconfig`, `Makefile`, dépendances de test et contrôle d'hygiène ;
- ajout d'un manifeste de migration SHA-256 pour les 101 fichiers de l'ancien répertoire.
