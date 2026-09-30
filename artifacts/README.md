# Local artifacts

Ce répertoire est réservé aux artefacts lourds ou générés qui ne doivent pas être suivis par Git :

- scans complets et corpus GP0 ;
- archives de handoff/release ;
- captures de logs et résultats bruts ;
- caches du jeu et états temporaires de probes ;
- packages ZIP générés.

Le contenu est ignoré par `.gitignore`, à l'exception de ce fichier.

Les artefacts historiques provenant de l'import initial restent disponibles dans l'archive source `smml.zip`. Leur SHA-256 et leur traitement sont consignés dans `docs/project/import-manifest.csv`.
