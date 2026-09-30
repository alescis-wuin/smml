# Sécurité, transactions et récupération

## Menaces opérationnelles réalistes

- jeu actif pendant mutation ;
- mise à jour Steam entre preflight et commit ;
- ancien mod/manager présent ;
- fichier vanilla modifié à la main ;
- crash/power loss au milieu d'un commit ;
- cache régénéré pendant une transaction ;
- save muté par une expérience ;
- symlink/path traversal ;
- deux processus SMML concurrents.

## Exigences de production

- lock exclusif global par installation (`flock` Linux ; abstraction Windows ultérieure) ;
- aucun symlink sur cibles gérées ;
- résolution/canonicalisation de chemin et interdiction de sortir des racines autorisées ;
- staging dans même filesystem que destination ;
- fichiers temporaires + flush/fsync + replace atomique ;
- journal write-ahead avec phase durable ;
- hash avant/après de chaque objet ;
- snapshot Save séparé des fichiers jeu ;
- rollback idempotent ;
- récupération explicite au redémarrage si journal incomplet ;
- quarantaine au lieu de suppression si ownership/drift incertain.

## Important : Steam Verify

Steam documente la vérification des fichiers installés ; notre observation locale montre qu'une installation précédente pouvait conserver 275 fichiers supplémentaires alors que tous les fichiers communs correspondaient à l'installation fraîche. SMML ne doit donc jamais assimiler « Steam Verify exécuté » à « arbre canonique sans extras » : seul le scan/fingerprint local permet cette conclusion.
