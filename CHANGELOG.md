# Changelog

## Unreleased

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
