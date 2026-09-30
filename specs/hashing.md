# Hashing déterministe — spécification v1

**Algorithmes publics :** `sha256`, `smml.content-tree-sha256/1`  
**Statut :** GP1 Foundation / v1 — candidate freeze  
**Portée :** primitives de digest utilisées par `GameTargetIdentity`, `PackageManifest`, `Profile`, `Lockfile`, `TransactionJournal` et les futurs `GameTargetInspector` / `TransactionEngine`.

## 1. Objectif

SMML utilise plusieurs champs SHA-256 qui n'ont pas tous la même **sémantique**, même lorsqu'ils utilisent le même algorithme cryptographique.

La v1 distingue explicitement :

1. le digest d'une séquence d'octets exacte ;
2. le digest d'un fichier régulier exact ;
3. le fingerprint d'un ensemble déterministe de fichiers ;
4. le fingerprint exact d'une installation ;
5. le fingerprint canonique d'une installation après politique d'exclusion ;
6. le fingerprint d'un sous-arbre diagnostique ;
7. le fingerprint du `ManagedOutputSet` final.

Le but est d'éliminer toute ambiguïté entre **algorithme**, **ensemble d'entrée** et **rôle métier**.

## 2. Règles normatives

Les mots **DOIT**, **NE DOIT PAS**, **DEVRAIT** et **PEUT** sont normatifs.

### HSH-001 — SHA-256 d'octets exacts

L'identifiant :

```text
sha256
```

signifie SHA-256 appliqué aux **octets exacts fournis**, sans transformation préalable.

Le résultat DOIT être encodé en hexadécimal ASCII minuscule sur 64 caractères.

Aucune des opérations suivantes n'est implicite :

- décodage texte ;
- normalisation Unicode ;
- normalisation des fins de ligne ;
- suppression ou ajout de BOM ;
- parsing JSON ;
- re-sérialisation JSON ;
- décompression ;
- canonicalisation métier.

Ainsi, deux documents JSON sémantiquement équivalents mais ayant des octets différents PEUVENT avoir des digests différents.

### HSH-002 — Digest d'un fichier régulier

Le digest d'un fichier est le SHA-256 de son contenu exact, du premier au dernier octet.

La primitive de hashing ne décide pas qu'un chemin est sûr à ouvrir. L'acquisition filesystem conforme appartient à `PathPolicy`, au futur `GameTargetInspector` ou au `TransactionEngine` : racine de confiance, no-follow, type `regular-file`, casse exacte et stabilité de l'observation doivent être établis par la couche appelante.

### HSH-003 — Record de contenu

`smml.content-tree-sha256/1` consomme un ensemble de records :

```text
path
size
sha256
```

avec les règles suivantes :

- `path` DOIT être un chemin logique valide selon `PathPolicy v1` ;
- `path` est relatif à la racine sémantique déclarée par le rôle du fingerprint ;
- `size` DOIT être un entier >= 0 ;
- `sha256` DOIT être le digest SHA-256 exact du contenu du fichier ;
- seuls des fichiers réguliers sont représentés ;
- un répertoire, symlink, reparse point ou autre type n'a pas de record de contenu v1.

### HSH-004 — Unicité portable des chemins

Dans un même ensemble de records :

- un chemin exact NE DOIT PAS apparaître deux fois ;
- deux chemins distincts ayant la même `PortableCollisionKey` selon `PathPolicy v1` NE DOIVENT PAS coexister.

Une collision est une erreur de construction de l'ensemble ; elle ne doit jamais être résolue arbitrairement par l'ordre des records.

### HSH-005 — Ordre déterministe

Les records sont triés par :

1. `PortableCollisionKey(path)` ;
2. les octets UTF-8 du chemin exact.

`PortableCollisionKey` utilise la sémantique figée par `PathPolicy v1`, notamment Unicode Default Case Folding 15.1.0.

L'ordre d'énumération du filesystem, de lecture JSON, d'archive ou de découverte NE DOIT PAS influencer le résultat.

### HSH-006 — Encodage du record

Pour chaque record trié, les octets suivants sont ajoutés au flux de hash :

```text
<path UTF-8> NUL <size décimale ASCII> NUL <sha256 ASCII minuscule> LF
```

Plus formellement :

```text
UTF8(path)
0x00
ASCII(decimal(size))
0x00
ASCII(lowercase_sha256)
0x0A
```

`decimal(size)` est la représentation décimale canonique d'un entier : `0` pour zéro, sinon aucun zéro initial.

Le fingerprint est :

```text
SHA256(concat(records encodés))
```

et l'identifiant d'algorithme est :

```text
smml.content-tree-sha256/1
```

### HSH-007 — Ensemble vide

L'ensemble vide est valide pour la primitive générique.

Il donne :

```text
fileCount      = 0
totalFileBytes = 0
sha256         = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

Une couche métier PEUT imposer qu'un ensemble particulier, par exemple une installation de jeu reconnue, soit non vide.

### HSH-008 — Résumé d'arbre

Lorsqu'un objet métier expose les trois valeurs, elles sont toutes dérivées du **même ensemble de records** :

```text
algorithm      = smml.content-tree-sha256/1
sha256         = fingerprint de l'ensemble
fileCount      = nombre de records
totalFileBytes = somme des size
```

`fileCount` et `totalFileBytes` ne sont jamais des entrées du hash ; ce sont des diagnostics dérivés.

### HSH-009 — Rôles de fingerprint

Les rôles v1 utilisent les primitives comme suit.

#### `installationExactFingerprint`

Ensemble de tous les fichiers réguliers suivis par le `GameTargetInspector` sous la racine du jeu, avant politique canonique. Les chemins des records sont relatifs au game root.

Les artefacts runtime suivis participent donc au résultat.

#### `canonicalGameFingerprint`

Même inventaire de départ que le fingerprint exact, filtré exclusivement par la politique versionnée `canonicalPolicy`.

Aucune exclusion heuristique implicite n'est autorisée.

#### `rootFingerprint`

Sous-ensemble des records exacts correspondant à :

```text
path == root
ou
path commence par root + "/"
```

**Les chemins encodés restent relatifs au game root.** Ils ne sont pas réécrits relativement à la racine sélectionnée. Cette règle conserve la sémantique des fingerprints GP0 historiques.

#### `targetFingerprint`

SHA-256 brut des octets du fichier cible ; ce n'est pas un fingerprint d'arbre.

#### `finalContentFingerprint`

Fingerprint `smml.content-tree-sha256/1` du `ManagedOutputSet` final staged. Les chemins sont relatifs au game root.

Le `ManagedOutputSet` contient uniquement les fichiers réguliers dont l'état final est produit ou sélectionné par SMML pour le profil : fichiers vanilla reconstruits/hookés, sorties du Composer et fichiers de packages gérés. Les fichiers baseline inchangés et les chemins supprimés n'y figurent pas.

### HSH-010 — Filtrage canonique

Une politique canonique est appliquée à des chemins déjà valides selon `PathPolicy v1`.

Les comparaisons de `excludedExactFiles` et `excludedFilePrefixes` sont **exactes et sensibles à la casse** sur le chemin logique NFC. Elles n'utilisent pas `PortableCollisionKey` pour masquer une différence de casse observée.

Cela garantit qu'une casse inattendue reste visible comme drift au lieu d'être silencieusement exclue.

La politique DOIT déclarer :

```text
contentTreeAlgorithm = smml.content-tree-sha256/1
```

### HSH-011 — Pas de domain separation en v1

Pour préserver les fingerprints GP0 déjà établis, v1 n'ajoute aucun préfixe de domaine dans le flux SHA-256.

Par conséquent, deux rôles différents appliqués au **même ensemble exact de records** produisent la même valeur SHA-256.

La signification d'un digest provient donc de son champ et de son contexte (`installationExactFingerprint`, `canonicalGameFingerprint`, `finalContentFingerprint`, etc.), pas de la valeur seule.

Une éventuelle domain separation nécessiterait un nouvel identifiant d'algorithme, par exemple `/2`.

### HSH-012 — Digests de documents et packages

Les digests suivants utilisent `sha256` sur les octets exacts, sans canonicalisation JSON :

```text
Profile.profileDigest
PackageManifest.manifestDigest
Package.packageDigest
PackageManifest.files[].sha256
Lockfile.artifacts[].sha256
TransactionJournal.before.sha256 / after.sha256
GameTargetIdentity.targetFingerprints[].sha256
```

`packageDigest` porte sur l'artefact package distribué exact, par exemple les octets du ZIP si le package distribué est un ZIP. Il ne s'agit pas du fingerprint de son contenu extrait.

### HSH-013 — Stabilité d'acquisition hors primitive

Une fonction qui hash une séquence d'octets ou une liste de records est déterministe.

La lecture d'un fichier vivant peut en revanche subir une modification concurrente. Le futur `GameTargetInspector` et le `TransactionEngine` DOIVENT définir une acquisition fail-closed permettant de détecter un changement pendant l'observation. Hashing v1 ne prétend pas résoudre cette course par lui-même.

### HSH-014 — Comparaison des fingerprints

Deux fingerprints ne sont comparables comme preuve d'identité que si :

1. leur algorithme est identique ;
2. leur rôle métier est compatible ;
3. leur ensemble d'entrée est défini par les mêmes règles ;
4. pour un fingerprint canonique, la même politique canonique est utilisée.

Comparer uniquement deux chaînes SHA-256 sans vérifier leur contexte est insuffisant.

## 3. Vecteurs normatifs minimaux

### Octets bruts

```text
SHA256("")
= e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

SHA256("abc")
= ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
```

### Arbre de deux records

Entrées, dans n'importe quel ordre :

```text
Data/a.bin      size=3 sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Survival/b.lua  size=9 sha256=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
```

Résultat :

```text
fileCount      = 2
totalFileBytes = 12
sha256         = e4f4b92be733431df6632d27be6329ef30b865653044710293220fc2d43ba583
```

Les vecteurs exécutables complets sont dans `tests/hashing_vectors.json`.

## 4. Compatibilité GP0

Le scanner GP0 historique calculait déjà :

```text
path + NUL + size + NUL + sha256 + LF
```

et conservait les chemins relatifs au game root lors des fingerprints de racines.

Hashing v1 formalise cette convention et remplace la dépendance implicite au `str.casefold()` du runtime par `PortableCollisionKey`/Unicode 15.1.0.

Les valeurs GP0 B0/B1 restent des fixtures historiques. Leur reproduction complète par le futur `GameTargetInspector` nécessite l'inventaire B0/B1 complet, non présent dans le dépôt canonique actuel.

## 5. Codes d'erreur de référence

L'implémentation de référence utilise au minimum :

```text
HASH_BAD_INPUT
HASH_BAD_SHA256
HASH_NEGATIVE_SIZE
HASH_DUPLICATE_PATH
HASH_PATH_COLLISION
HASH_POLICY_ALGORITHM_MISMATCH
```

Les codes PathPolicy peuvent également remonter lorsqu'un chemin est invalide.

## 6. Invariants testables

Une implémentation conforme DOIT démontrer au minimum :

1. conformité aux vecteurs SHA-256 bruts ;
2. indépendance vis-à-vis de l'ordre des records ;
3. encodage exact `path NUL size NUL sha256 LF` ;
4. rejet d'un hash non minuscule/64 hex ;
5. rejet d'une taille négative ou non entière ;
6. rejet d'un chemin dupliqué ;
7. rejet d'une collision `PortableCollisionKey` ;
8. calcul correct de `fileCount` et `totalFileBytes` ;
9. fingerprint vide égal à SHA-256 de la chaîne vide ;
10. filtrage canonique exact et versionné ;
11. sous-arbre conservant les chemins game-root-relative ;
12. `ManagedOutputSet` utilisant exactement le même algorithme d'arbre ;
13. digests de Profile/manifest/package calculés sur les octets, sans re-sérialisation.

## 7. Hors périmètre v1

- acquisition filesystem atomique ou snapshot native ;
- parallélisation du hashing ;
- cache de digests ;
- BLAKE3 ou autre algorithme ;
- signature/authenticité des digests ;
- Merkle tree incrémental ;
- format du futur `StateManifest` ;
- implémentation finale du `GameTargetInspector`.
