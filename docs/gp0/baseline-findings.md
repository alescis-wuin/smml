# GP0.1 — Baseline et comportement d'installation

## Installation avant réinstallation

- 61 645 fichiers ; ~19.56 GiB.
- Après nouvelle installation : 61 370 fichiers ; ~19.18 GiB.
- Diff observée : **275 fichiers supprimés, 0 fichier ajouté, 0 fichier commun modifié**.
- Les 157 extras sous Survival ont été attribués aux mods actuels/historiques de l'utilisateur ; les « 38 autres » initialement ambigus ont été confirmés par l'utilisateur comme ses anciens mods.
- Conclusion : l'installation pouvait avoir tous les fichiers officiels corrects tout en conservant des extras de mods.

## B0 — baseline fraîche pré-lancement

- 61 370 fichiers ; 20 596 856 244 octets.
- fingerprint exact contenu : `6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964`.
- aucun marqueur des trois mods actuels.

## B1 — après premier lancement normal

- 61 371 fichiers ; seul `Logs/game-...log` ajouté ; 10 répertoires runtime créés ; aucun fichier B0 existant modifié.
- fingerprint exact : `9d5e06e5da64485218f8f9154097c1638719166c3e9d004adac77d01c2863ab4`.

## Conséquences

- `installationExactFingerprint` et `canonicalGameFingerprint` doivent être distincts.
- Steam Verify est un outil utile, mais la preuve de propreté de l'arbre local vient du scan SMML, pas de l'action « Verify » en elle-même.
- Baseline Vault doit être capturé seulement après validation de propreté.
- les artefacts runtime prouvés (Logs, certains dirs/cache) doivent être classés explicitement, jamais exclus par heuristique vague.
