# SMML PathPolicy v1

Identifiant normatif :

```text
smml.path-policy/1
```

## 1. Objet

`PathPolicy v1` définit une représentation unique et portable des chemins logiques SMML ainsi que les invariants minimaux à respecter avant toute lecture ou mutation d'un objet filesystem géré.

La politique s'applique notamment aux chemins présents dans :

- `GameTargetIdentity` ;
- `TransactionJournal` ;
- `PackageManifest` ;
- `HookPackManifest` ;
- les futurs manifests de contenu et états gérés.

Elle ne remplace pas les primitives OS de sûreté. La conversion d'un chemin logique en objet filesystem réel DOIT être réalisée par un backend capable de parcourir une racine de confiance sans suivre implicitement des liens.

## 2. Frontière conceptuelle

```text
SMML logical path
        ↓
PathPolicy lexical validation
        ↓
portable collision key
        ↓
trusted root + no-follow traversal
        ↓
filesystem object classification
        ↓
operation-specific authorization
```

Un chemin valide lexicalement n'autorise jamais, à lui seul, une lecture, une suppression ou une écriture.

## 3. Faits externes utilisés

Pour la compatibilité Windows, la v1 tient compte des règles Win32 documentées par Microsoft : caractères réservés, noms de périphériques historiques, absence de garantie de sensibilité à la casse et comportement problématique des noms terminés par un espace ou un point.

Source informative :

```text
https://learn.microsoft.com/windows/win32/fileio/naming-a-file
```

Les contraintes supplémentaires ci-dessous sont des **décisions de conception SMML**, volontairement plus conservatrices que certains filesystems natifs.

## 4. Chemin logique SMML

### PP-001 — Encodage et séparateur

Un chemin logique :

- est une chaîne Unicode ;
- DOIT être en forme Unicode NFC ;
- est sérialisé en UTF-8 ;
- utilise exclusivement `/` comme séparateur ;
- NE DOIT PAS contenir `\\`.

SMML NE DOIT PAS corriger automatiquement un séparateur Windows en `/`. Une entrée non canonique est rejetée.

### PP-002 — Relativité

Un chemin logique est toujours relatif à une racine fournie séparément.

Sont interdits :

- `/foo` ;
- `C:/foo` ;
- `C:foo` ;
- chemins UNC ;
- préfixes Win32/NT tels que `\\?\\` ou `\\.\\` ;
- toute autre syntaxe de namespace ou volume.

Le caractère `:` étant interdit dans chaque segment, les formes drive-relative et Alternate Data Streams sont également impossibles en v1.

### PP-003 — Segments

Chaque segment DOIT :

- être non vide ;
- être différent de `.` et `..` ;
- ne pas se terminer par un espace ASCII ;
- ne pas se terminer par `.` ;
- ne contenir aucun caractère ASCII de contrôle `U+0000..U+001F` ni `U+007F` ;
- ne contenir aucun des caractères Windows réservés `< > : " | ? *`.

Un point initial reste autorisé : `.smml`, `.cache` ou `.hidden/file` sont valides.

### PP-004 — Noms de périphériques Windows

Le nom de base de chaque segment, avant le premier `.`, est comparé sans tenir compte de la casse.

Les noms suivants sont interdits, avec ou sans extension :

```text
CON PRN AUX NUL
COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9
LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9
COM¹ COM² COM³
LPT¹ LPT² LPT³
```

Exemples invalides :

```text
NUL
nul.txt
COM1.json
lpt³.log
```

Exemples valides :

```text
COM10
LPT10.txt
configuration/NUL-value.json
```

### PP-005 — Limites portables v1

La v1 fixe les limites logiques suivantes :

```text
maxPathUtf8Bytes     = 4096
maxSegmentUtf8Bytes  = 255
maxSegments          = 256
```

Ces limites sont des bornes de sécurité/portabilité SMML. Le backend filesystem PEUT imposer une limite plus stricte si la racine réelle ou l'API OS l'exige ; il NE DOIT PAS accepter une entrée dépassant les limites v1.

## 5. Identité et collisions

### PP-006 — Chemin exact

Le chemin exact canonique est la chaîne NFC validée, sans réécriture de casse ou de ponctuation.

Les digests de manifests et inventaires utilisent cette forme exacte.

### PP-007 — PortableCollisionKey

Pour détecter les chemins qui pourraient désigner le même objet dans un environnement insensible à la casse, SMML calcule :

```text
PortableCollisionKey(path) = NFC(DefaultCaseFold_Unicode_15.1.0(NFC(path)))
```

La table de case folding normative est Unicode `15.1.0`, cohérente avec `GameTargetIdentity v1`.

#### Compatibilité de l'implémentation Python de référence

La **sémantique normative reste Unicode 15.1.0**. L'implémentation Python de référence PEUT toutefois s'exécuter avec une bibliothèque standard exposant UCD `15.0.0` ou `15.1.0`, à condition de vérifier au démarrage les invariants de compatibilité utilisés par PathPolicy.

Cette exception est bornée à ces deux versions. Elle repose sur les faits suivants :

- `PortableCollisionKey` utilise le **full/default case folding**, pas `Simple_Case_Folding` ;
- le full case folding est stable pour les caractères déjà assignés ;
- Unicode 15.1 ajoute 622 idéogrammes CJK et cinq Ideographic Description Characters, qui sont sans casse et sans effet de normalisation NFC ;
- les ajouts `Simple_Case_Folding` de Unicode 15.1 ne changent donc pas le full/default case folding requis ici ;
- la normalisation des caractères déjà assignés est couverte par la stabilité Unicode de NFC.

L'implémentation de référence DOIT vérifier explicitement ces propriétés avant d'accepter une runtime UCD `15.0.0`. Toute autre version UCD est rejetée en v1 afin d'éviter qu'un caractère assigné après Unicode 15.1 acquière silencieusement une sémantique de casse différente de la politique figée.

Une collection de chemins gérés NE DOIT PAS contenir deux chemins distincts possédant la même `PortableCollisionKey`.

Exemples de collisions :

```text
Foo/Bar.lua
foo/bar.lua
```

et, selon Unicode case folding :

```text
Straße.txt
STRASSE.TXT
```

Le rejet est volontaire même sur un filesystem local sensible à la casse.

### PP-008 — Aucune normalisation silencieuse

SMML rejette une entrée non NFC. Il NE DOIT PAS :

- trim les espaces ;
- retirer les points finaux ;
- résoudre `.` ou `..` ;
- convertir `\\` en `/` ;
- modifier la casse ;
- décoder des séquences URL.

Une transformation silencieuse ferait perdre la provenance exacte et pourrait créer des collisions dépendantes de plateforme.

## 6. Racines de confiance et containment

### PP-009 — Racine externe au chemin logique

Une opération filesystem reçoit séparément :

```text
TrustedRoot
LogicalPath
OperationIntent
```

La racine absolue locale NE DOIT PAS être sérialisée dans un package ou un lockfile portable.

### PP-010 — Racine de confiance

Avant résolution, le backend DOIT établir que la racine :

- existe ;
- est un répertoire ;
- n'est pas un symlink ;
- n'est pas un reparse point redirigeant le parcours ;
- correspond à la racine attendue par l'appelant.

La façon d'attester l'identité de la racine est spécifique à l'OS et appartient au futur backend filesystem.

### PP-011 — Parcours no-follow

Chaque composant existant entre la racine et la cible DOIT être inspecté sans suivre implicitement un symlink/reparse point.

Un simple :

```text
normalize(root + "/" + path)
```

ou test de préfixe de chaîne n'est pas une preuve suffisante de containment.

L'implémentation de production devra privilégier une résolution relative à un handle/descripteur de racine et des primitives `no-follow` lorsque disponibles.

### PP-012 — Case exacte des objets existants

Lorsqu'un composant existe, son nom observé DOIT correspondre exactement au segment logique demandé.

Une différence uniquement de casse est une erreur `CASE_MISMATCH`, même sur un filesystem qui aurait accepté l'accès.

Cela évite que le même lockfile ou journal désigne des objets différents selon le host.

## 7. Types d'objets filesystem

### PP-013 — Classification minimale

Le backend DOIT pouvoir distinguer au minimum :

```text
missing
regular-file
directory
symlink
reparse-point
other
```

Une erreur d'inspection NE DOIT PAS être transformée en `missing`.

### PP-014 — Symlinks et reparse points

Un symlink ou reparse point rencontré sur une cible ou un ancêtre géré est rejeté en v1.

Le backend NE DOIT PAS suivre l'objet pour obtenir le hash de sa destination.

### PP-015 — Hardlinks

Un fichier régulier existant destiné à être muté DOIT avoir un seul lien filesystem connu (`linkCount == 1`) lorsque l'OS permet cette vérification.

Si le backend détecte plusieurs hardlinks, l'écriture est refusée : modifier le fichier pourrait modifier silencieusement un autre chemin.

Pour les packages archivés, une entrée déclarée comme hardlink est rejetée par le futur `PackageValidator`.

### PP-016 — Type attendu

L'appelant fournit un type attendu pour la feuille :

```text
regular-file
regular-file-or-missing
directory
directory-or-missing
```

Une autre classe observée produit une erreur ; elle n'est jamais remplacée implicitement.

## 8. Intentions d'accès

La politique distingue au minimum :

```text
inspect
create
replace
delete
```

- `inspect` ne confère aucun droit de mutation ;
- `create` exige une feuille absente et des ancêtres sûrs ;
- `replace` exige une feuille `regular-file`, sûre et non hardlinkée ;
- `delete` exige une feuille `regular-file`, sûre et dont l'ownership/hash est validé par la couche supérieure.

`PathPolicy` ne décide ni l'ownership ni les hashes attendus ; ces responsabilités restent à `TransactionJournal` / `TransactionEngine` / State Manager.

## 9. Codes d'erreur v1

Une implémentation PEUT enrichir le diagnostic, mais les catégories suivantes sont stables pour les tests :

```text
PATH_EMPTY
PATH_NOT_UTF8
PATH_NOT_NFC
PATH_TOO_LONG
TOO_MANY_SEGMENTS
SEGMENT_TOO_LONG
ABSOLUTE_OR_NAMESPACED_PATH
BACKSLASH_FORBIDDEN
EMPTY_SEGMENT
DOT_SEGMENT
CONTROL_CHARACTER
RESERVED_CHARACTER
TRAILING_DOT_OR_SPACE
RESERVED_DEVICE_NAME
CASE_COLLISION
ROOT_UNTRUSTED
OUTSIDE_ROOT
CASE_MISMATCH
SYMLINK_FORBIDDEN
REPARSE_POINT_FORBIDDEN
HARDLINK_FORBIDDEN
TYPE_MISMATCH
INSPECTION_FAILED
```

## 10. Interaction avec les contrats existants

### GameTargetIdentity

Les chemins de `rootFingerprints` et `targetFingerprints` utilisent `PathPolicy v1` avant hashing.

### TransactionJournal

`operation.path` utilise `PathPolicy v1`. La présence d'un chemin valide ne remplace pas les contrôles `beforeHash/afterHash` ni l'observation du type filesystem.

### PackageManifest

Tous les chemins de `files`, `entrypoints` et `artifacts` utilisent `PathPolicy v1`. Le futur `PackageValidator` doit en plus inspecter le type réel des entrées d'archive.

### HookPackManifest

Les chemins `targetFiles` et `cacheConsequences` utilisent `PathPolicy v1`. Aucun Hook Pack ne peut assouplir la politique.

### CanonicalGamePolicy

Les chemins exacts et les préfixes exclus utilisent les mêmes règles lexicales ; un préfixe se termine par `/` dans le document, mais sa partie chemin est validée par `PathPolicy v1`.

## 11. Invariants testables

Une implémentation conforme DOIT au minimum démontrer :

1. rejet des chemins vides, non encodables UTF-8, absolus, drive-relative/absolute et namespaced ;
2. rejet de `\\`, `//`, `.` et `..` ;
3. NFC obligatoire ;
4. rejet des contrôles ASCII et caractères Windows réservés ;
5. rejet d'un segment terminé par espace ou point ;
6. rejet des noms device Windows avec extension ;
7. respect des limites UTF-8 v1 ;
8. `PortableCollisionKey` normatif basé sur Unicode 15.1.0, avec compatibilité de référence vérifiée UCD 15.0.0/15.1.0 ;
9. détection de collisions casefold/NFC indépendamment du host ;
10. absence de normalisation silencieuse ;
11. symlinks/reparse points rejetés sur les chemins gérés ;
12. hardlinks refusés pour une mutation ;
13. différence de casse d'un objet existant refusée ;
14. aucune décision d'ownership ou de hash n'est prise par PathPolicy seul.

## 12. Hors périmètre v1

- implémentation OS finale de traversal par handle ;
- politique de durabilité (`fsync`, `FlushFileBuffers`, atomic replace) ;
- lock inter-processus ;
- détection d'attaques TOCTOU entre inspection et mutation ;
- ownership / State Manifest ;
- limites de taille/nombre/ratio des packages ;
- support d'archives symlink/hardlink ;
- gestion des short names 8.3 existants ;
- volumes réseau et filesystems exotiques ;
- opérations sur répertoires dans `TransactionJournal v1`.

## 13. Références informatives Unicode

- Unicode Character Encoding Stability Policies — normalization et case folding stability : `https://www.unicode.org/standard/stability_policy.html`
- Unicode 15.1 announcement — 622 CJK Unified Ideographs Extension I + 5 Ideographic Description Characters : `https://blog.unicode.org/2023/09/announcing-unicode-standard-version-151.html`
- UTC #175 — ajouts `Simple_Case_Folding` 15.1 pour U+1FD3, U+1FE3 et U+FB05 : `https://www.unicode.org/L2/L2023/23076.htm`
