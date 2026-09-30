# GameTargetIdentity — spécification v1

**Schema ID :** `smml.game-target/1`  
**Statut :** GP1 Foundation / v1 — candidate freeze  
**Portée :** identité d'une installation cible avant sélection d'un Hook Pack ou mutation SMML.

## 1. Objectif

`GameTargetIdentity` décrit la cible de jeu avec plusieurs preuves indépendantes. Un numéro de version seul n'est jamais suffisant pour autoriser une mutation.

La v1 encode :

1. l'identité Steam ;
2. la version du jeu et le build moteur ;
3. le Steam build et la branche ;
4. l'environnement hôte/jeu et la couche de compatibilité ;
5. un fingerprint exact de l'installation ;
6. un fingerprint canonique calculé avec une politique versionnée ;
7. des fingerprints de racines ;
8. des fingerprints de fichiers cibles critiques.

Les anchors de patch ne font pas partie de `GameTargetIdentity`. Ils appartiennent au futur `HookPackManifest`.

## 2. Règles normatives

Les mots **DOIT**, **NE DOIT PAS**, **DEVRAIT** et **PEUT** sont normatifs.

### GTI-001 — Version du schéma

`schema` DOIT valoir exactement :

```text
smml.game-target/1
```

### GTI-002 — Steam AppID

`steamAppId` DOIT être un entier strictement positif.

Pour Scrap Mechanic, la valeur actuellement validée est `387990`.

### GTI-003 — Métadonnées de build

`gameVersion`, `engineBuild`, `steamBuildId` et `steamBranch` DOIVENT être présents.

`steamBuildId` est sérialisé comme une chaîne car il s'agit d'un identifiant, pas d'une quantité numérique.

### GTI-004 — Plateformes

`platform.hostOs` décrit l'OS hôte.

`platform.gameOs` décrit la plateforme du binaire de jeu exécuté.

`platform.compatibilityLayer.kind` décrit la couche utilisée entre les deux.

Si `hostOs != gameOs`, `compatibilityLayer.kind` NE DOIT PAS être `none`.

Si `compatibilityLayer.kind == none`, `hostOs` et `gameOs` DOIVENT être identiques.

La version d'une couche de compatibilité PEUT être omise lorsqu'elle n'est pas établie par les preuves disponibles.

### GTI-005 — Chemins

Tous les chemins dans `rootFingerprints` et `targetFingerprints` :

- DOIVENT être relatifs au game root ;
- DOIVENT utiliser `/` comme séparateur ;
- NE DOIVENT PAS être absolus ;
- NE DOIVENT PAS contenir `.` ou `..` comme segment ;
- NE DOIVENT PAS contenir de `\\` ;
- NE DOIVENT PAS contenir de NUL ;
- NE DOIVENT PAS former de collision insensible à la casse dans une même collection.

L'orthographe originale du chemin est conservée.

### GTI-006 — Hashes

Tous les SHA-256 DOIVENT être encodés en hexadécimal minuscule sur 64 caractères.

Les primitives et rôles de digest sont définis normativement par [`hashing.md`](hashing.md). Un hash de fichier (`sha256`) et un fingerprint d'arbre (`smml.content-tree-sha256/1`) ne sont pas interchangeables.

### GTI-007 — Fingerprint exact

`fingerprints.installationExactFingerprint` DOIT représenter tous les fichiers suivis de l'installation observée.

Il sert à l'audit exact. Un artefact runtime supplémentaire peut donc le modifier.

### GTI-008 — Fingerprint canonique

`fingerprints.canonicalGameFingerprint` DOIT être calculé avec la politique indiquée par `fingerprints.canonicalPolicy`.

Cette politique :

- DOIT être explicite ;
- DOIT être versionnée ;
- NE DOIT exclure que des artefacts classifiés comme non structurants ;
- NE DOIT PAS utiliser une heuristique implicite du type « ignorer tout Cache ».

### GTI-009 — Fingerprints partiels

`rootFingerprints` contient des fingerprints exacts de racines utiles au diagnostic. Chaque entrée DOIT déclarer `algorithm = smml.content-tree-sha256/1`. Leur présence n'autorise pas à elle seule une mutation.

Pour préserver la sémantique GP0, les records d'un sous-arbre conservent leurs chemins **relatifs au game root** ; ils ne sont pas réécrits relativement à la racine sélectionnée. La sélection d'une racine `R` retient `path == R` ou `path` commençant par `R + "/"`.

### GTI-010 — Cibles critiques

`targetFingerprints` contient les SHA-256 bruts des fichiers utilisés comme preuves fortes de compatibilité, par exemple les cibles de Hook Pack. Chaque entrée DOIT déclarer `algorithm = sha256`.

Un Hook Pack ne doit pas être sélectionné uniquement avec `gameVersion` ou `steamBuildId`.

### GTI-011 — Algorithme d'arbre

La v1 utilise :

```text
smml.content-tree-sha256/1
```

Sa définition normative complète est dans [`hashing.md`](hashing.md). En résumé, chaque record contient `path + size + sha256`, les chemins doivent être valides et uniques selon `PathPolicy v1`, l'ordre est déterministe via `PortableCollisionKey`, et l'encodage est :

```text
<path UTF-8> NUL <size décimale ASCII> NUL <sha256 minuscule ASCII> LF
```

Un chemin dupliqué ou une collision portable est une erreur ; le hash ne doit pas les départager arbitrairement.

### GTI-012 — Relation exact/canonique

Les deux fingerprints sont conceptuellement distincts même lorsqu'ils ont la même valeur.

Le nombre de fichiers et le nombre d'octets du fingerprint canonique NE DOIVENT PAS dépasser ceux du fingerprint exact correspondant.

### GTI-013 — Autorisation de mutation

Un `GameTargetIdentity` valide structurellement n'est pas, à lui seul, une autorisation de mutation.

La future sélection de Hook Pack devra combiner au minimum :

```text
metadata
+ fingerprints
+ target preconditions
+ anchors
+ structural validation
```

## 3. Politiques canoniques

### `smml.canonical-game-policy/1` — historique

La v1 exclut uniquement :

```text
Logs/
```

Elle reste reconnue pour relire les preuves GP0/GP1 antérieures.

### `smml.canonical-game-policy/2` — active

La v2 exclut explicitement :

```text
Cache/
Logs/
```

Cette révision est fondée sur une nouvelle preuve locale :

- le corpus B0 contient 20 119 fichiers sous `Cache/`, tous classés `reference_only:generated_cache` par la capture GP0 ;
- le fingerprint de `Cache/` est identique entre B0 et B1 ;
- une inspection ultérieure de la même Steam build observe un drift de `Cache/` alors que les fichiers cibles critiques conservent leurs SHA-256 GP0 ;
- B1 n'ajoute qu'un fichier sous `Logs/` et ne modifie aucun fichier B0.

`Cache/` est donc classé **rebuildable-cache** pour l'identité canonique et `Logs/` **runtime-ephemeral**. Cette classification n'affaiblit pas les preuves de fichier : un fichier de cache peut rester présent dans `targetFingerprints`.

En particulier :

```text
Cache/Bundle/core_data.cbo
```

reste une target critique avec SHA-256 exact malgré l'exclusion de `Cache/` du fingerprint canonique.

La politique NE DOIT PAS transformer cette exclusion en permission de purge globale. L'invariant « invalidation ciblée et prouvée » reste inchangé.

## 4. Fixture de référence 1.0.6.889

Faits GP0 réutilisés :

```text
steamAppId   = 387990
gameVersion  = 1.0.6
engineBuild  = 889
steamBuildId = 25442087
steamBranch  = public

B0 exact = 6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964
B1 exact = 9d5e06e5da64485218f8f9154097c1638719166c3e9d004adac77d01c2863ab4
```

Avec `smml.canonical-game-policy/2`, B0 et B1 produisent le même fingerprint canonique : `f8356e5f0b660320bdcd196bc553114d688aeff43f20872438cbac1e1bc9668c` (41 251 fichiers, 15 342 231 607 octets). La v1 historique produit toujours le fingerprint B0 exact après exclusion du seul log B1.

La version Proton exacte n'est pas établie dans le handoff et n'est donc pas inventée dans l'exemple.

## 5. Limite de compatibilité du tri GP0

Le scanner GP0 historique utilisait `str.casefold()` pour l'ordre. Les fingerprints B0/B1 de référence sont conservés comme fixtures héritées. La spécification v1 fixe désormais Unicode 15.1.0 afin d'éviter qu'une future implémentation change d'ordre au gré d'une mise à jour de runtime.

Le manifeste complet B0 est désormais conservé sous forme sanitizée dans `evidence/gp0/baselines/b0-file-inventory.json.gz`. Les tests recalculent bit-à-bit le fingerprint B0 historique et le fingerprint canonique v2 depuis ces 61 370 records.

## 6. Hors périmètre v1

- anchors de Hook Pack ;
- règles de sélection complète du Hook Pack ;
- handshake multijoueur ;
- signature/authenticité des preuves ;
- politique complète PathPolicy Windows/POSIX ;
- TransactionJournal ;
- identité d'un état géré SMML.
