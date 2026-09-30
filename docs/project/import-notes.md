# Notes d'import du dépôt Git

Le répertoire d'origine ne contenait pas de dépôt Git. La réorganisation ne prétend donc pas reconstruire un historique de commits original qui n'existait pas.

## Ce qui a été conservé

- dernière version disponible des sources GP0 utiles ;
- documents GP0/architecture uniques issus du handoff v3 ;
- preuves compactes nécessaires pour soutenir les décisions ;
- snapshot GP1 Foundation v0.6.0 éclaté en `specs/`, `schemas/`, `policies/`, `examples/`, `tests/`.

## Ce qui n'est plus dans l'arbre suivi

- archives GP1 v0.2.0 à v0.6.0 ;
- handoffs ZIP v2/v3 ;
- versions historiques manuelles des scanners/probes ;
- scans/corpus de plusieurs dizaines de Mo ;
- états temporaires, backups/quarantine de probes ;
- ZIP de résultats ;
- `__pycache__`/`.pyc` ;
- événements GP0.5 bruts contenant notamment des noms de joueurs.

Ces artefacts ne sont pas détruits : ils restent dans l'archive source `smml.zip`. Le fichier `import-manifest.csv` conserve leur chemin, taille, SHA-256 et décision de migration.

À partir de ce point, les évolutions de sources doivent passer par Git plutôt que par duplication de fichiers suffixés par une version.
