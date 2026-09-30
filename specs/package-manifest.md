# SMML PackageManifest v1

Statut : **candidate freeze** pour GP1 Foundation.

Identifiant de schéma :

```text
smml.package-manifest/1
```

JSON Schema :

```text
urn:smml:schema:package-manifest:1
```

## 1. Objet

`PackageManifest v1` décrit ce qu'un package SMML **déclare** : identité permanente, version, compatibilité, relations de résolution, capabilities, ordre relatif, impact de persistance, entrypoints, artefacts et inventaire de fichiers.

Le manifest n'est ni :

- un lockfile ;
- un état d'installation ;
- un journal transactionnel ;
- une preuve que le package est sûr ;
- une autorisation d'écriture dans l'installation du jeu.

Le `PackageValidator` reste responsable de vérifier le conteneur réel, les chemins, les types d'objets filesystem, les tailles, les collisions et les digests avant que le Resolver ou le Transaction Engine ne puissent consommer le package.

## 2. Sources et décisions

### PM-001 — Identité permanente

`id` est l'identité logique permanente du package.

La v1 impose un identifiant ASCII en minuscules de forme reverse-DNS / namespace stable, par exemple :

```text
com.example.pallet64
```

Une fois publié, un `id` NE DOIT PAS être réutilisé pour un autre projet.

`name` est humain et mutable ; il ne participe pas à l'identité logique.

### PM-002 — Version SemVer

`version` DOIT être une version SemVer 2.0.0 stricte.

La version du package est indépendante de la version de Scrap Mechanic.

Les métadonnées SemVer `+build` NE MODIFIENT PAS la précédence.

### PM-003 — Grammaire de range SMML v1

SMML v1 définit volontairement une grammaire minimale et ne dépend pas implicitement de npm, NuGet ou d'un autre package manager.

Formes autorisées :

```text
*
1.2.3
>=1.2.3 <2.0.0
>1.0.0 <=1.9.9
=1.2.3
```

Une séquence de comparateurs séparés par un ou plusieurs espaces ASCII `U+0020` est un **AND**. Les espaces de début/fin et les autres caractères de whitespace ne sont pas autorisés.

Opérateurs v1 :

```text
=
>
>=
<
<=
```

Ne sont PAS définis en v1 :

```text
^
~
||
virgules
versions partielles 1.2
wildcards 1.x
hyphen ranges
```

Un range exact `1.2.3` est équivalent à `=1.2.3` en termes de précédence SemVer. Les métadonnées `+build` sont donc ignorées pour l'évaluation du range, mais restent présentes dans l'identité textuelle de la version du package.

Les préversions sont comparées directement selon les règles de précédence SemVer. SMML v1 n'ajoute pas de règle spéciale de filtrage des préversions de type npm.

### PM-004 — Compatibilité jeu

`compatibility.targets` contient un ou plusieurs sélecteurs.

Les sélecteurs sont combinés en **OR** : au moins un sélecteur doit correspondre.

À l'intérieur d'un sélecteur, tous les champs présents sont combinés en **AND**.

`steamAppId` est obligatoire. Les contraintes suivantes sont optionnelles et exactes :

- `gameVersions` ;
- `engineBuilds` ;
- `steamBuildIds` ;
- `steamBranches` ;
- `canonicalGameFingerprints` ;
- `hostOs` ;
- `gameOs` ;
- `compatibilityLayers`.

`gameVersion` dans `GameTargetIdentity` est une chaîne opaque. `PackageManifest v1` NE LUI APPLIQUE PAS SemVer. Une compatibilité par version de jeu est donc une liste de valeurs exactes.

Les contraintes par fingerprint canonique utilisent la valeur `fingerprints.canonicalGameFingerprint.sha256` de `GameTargetIdentity`.

La présence d'un sélecteur compatible ne suffit pas à autoriser un Hook Pack. Les anchors, preconditions et fingerprints de cibles critiques restent du ressort de `HookPackManifest`.

### PM-005 — Dépendances

Chaque dépendance contient :

```text
id
range
kind = hard | soft
```

`hard` : absence ou incompatibilité bloque la résolution du package.

`soft` : absence n'empêche pas le package d'être résolu ; si la dépendance est présente et compatible, le Resolver peut l'utiliser pour l'ordre et l'explicabilité.

Un package NE DOIT PAS dépendre de lui-même.

Un même `id` de dépendance NE DOIT apparaître qu'une fois dans le manifest v1. Une seule relation porte donc la contrainte complète et son caractère hard/soft.

### PM-006 — Capabilities

Les capabilities sont identifiées séparément des packages. Leur `id` suit la même discipline de namespace ASCII lower-case afin d'éviter les variantes de casse ambiguës.

Une capability v1 utilise :

```text
id
version entière >= 1
```

La clé canonique est :

```text
<id>@<version>
```

Exemple :

```text
smml.storage@1
```

`capabilities.provides` déclare les capabilities fournies par le package.

`capabilities.requires` déclare les capabilities consommées et leur cardinalité :

```text
exactlyOne  = exactement 1 provider
zeroOrOne   = 0 ou 1 provider
oneOrMore   = au moins 1 provider
many        = 0 à N providers
```

La sélection effective des providers appartient au Resolver et sera figée dans le Lockfile.

Un même couple `id@version` NE DOIT PAS apparaître deux fois dans `provides` ni deux fois dans `requires`.

### PM-007 — Conflits

`conflicts.packages` contient des conflits package + range SemVer.

`conflicts.capabilities` contient des conflits capability + version.

Un package NE DOIT PAS se déclarer en conflit avec lui-même.

Un package NE DOIT PAS fournir une capability qu'il déclare simultanément comme conflictuelle au même `id@version`.

Le Resolver NE DOIT PAS résoudre un conflit par une politique implicite « dernier package gagne ».

### PM-008 — Ordre relatif

`loadBefore` et `loadAfter` contiennent des IDs de packages.

Le package courant NE DOIT PAS s'y référencer lui-même.

Un même ID NE DOIT PAS être présent dans les deux listes.

Ces relations sont des contraintes de graphe. L'ordre final reste celui du Resolver : dépendances, providers, conflits, contraintes explicites, tri topologique et tie-break déterministe.

L'ordre de découverte sur le filesystem n'a aucune valeur sémantique.

### PM-009 — Impact de persistance

`persistenceImpact` utilise l'échelle GP1 :

```text
none
runtimeState
playerState
worldContent
```

`worldContent` signifie qu'une désactivation ou désinstallation peut affecter un monde qui référence déjà des UUID/objets fournis par le package. Cela doit déclencher des politiques plus strictes dans les couches supérieures.

La valeur est déclarative ; elle ne remplace pas l'analyse des contributions ni les politiques du Profile.

### PM-010 — Entrypoints

`entrypoints` est optionnel et peut déclarer :

```text
shared
server
client
```

Chaque valeur est un chemin relatif dans le package et DOIT être présente dans `files`.

Le manifest ne définit pas encore la signature runtime de ces scripts. Cette sémantique appartiendra aux contrats Runtime/SDK.

### PM-011 — Artefacts référencés

`artifacts` référence les descripteurs machine-readable portés par le package sans imposer leur schéma métier dans `PackageManifest`.

Chaque entrée contient :

```text
id
type
path
```

`type` est un identifiant extensible, par exemple :

```text
smml.contract-descriptor/1
smml.hook-pack-manifest/1
smml.content-contribution/1
```

`path` DOIT être présent dans `files`.

`id` DOIT être unique dans le package. Un même fichier NE DOIT PAS être utilisé comme chemin de plusieurs artefacts v1 afin de conserver une provenance non ambiguë.

Le contenu de ces artefacts est validé par leur propre schéma.

### PM-012 — Inventaire de fichiers

`files` contient les fichiers distribués couverts par le manifest :

```text
path
size
sha256
```

Chaque chemin :

- est relatif à la racine du package ;
- utilise `/` ;
- ne contient ni `.` ni `..` comme segment ;
- n'est pas absolu ;
- est unique en comparaison case-insensitive.

`smml.package.json` DOIT être encodé en UTF-8 sans BOM. Il NE DOIT PAS figurer dans `files`, car son inclusion avec son propre digest créerait une dépendance circulaire.

Le futur `PackageValidator` DOIT vérifier que l'inventaire correspond exactement aux fichiers distribués qui doivent être couverts, après application de la politique de conteneur.

### PM-013 — Identité cryptographique dérivée

Les valeurs suivantes sont **dérivées**, pas auto-déclarées dans le manifest :

```text
manifestDigest = SHA-256 des octets exacts de smml.package.json
packageDigest  = SHA-256 des octets exacts de l'artefact package distribué
fileDigests    = valeurs sha256 déclarées dans files, vérifiées sur les octets extraits
```

Cela évite toute auto-référence de hash. Ces trois digests utilisent la primitive `sha256` d'octets exacts définie dans [`hashing.md`](hashing.md) ; aucun parsing/reformatage JSON n'est autorisé avant calcul.

L'identité exacte d'un package résolu est au minimum :

```text
id
version
packageDigest
manifestDigest
```

Deux artefacts ayant le même `id` et la même `version` mais un `packageDigest` différent NE DOIVENT PAS être traités comme équivalents. Le Resolver/Lockfile devra considérer cette situation comme ambiguë ou incompatible tant qu'une provenance exacte n'est pas choisie explicitement.

### PM-014 — Sécurité et autorité

La validité du JSON Schema et des invariants sémantiques du manifest ne prouve pas la sûreté du package.

Avant consommation, le `PackageValidator` devra notamment traiter :

- zip-slip / `../` ;
- chemins absolus ;
- symlinks et reparse points ;
- hardlinks si applicables ;
- noms réservés Windows ;
- collisions case-insensitive ;
- duplicate normalized paths ;
- limites de nombre de fichiers ;
- taille décompressée ;
- ratio de compression ;
- racines inattendues ;
- correspondance taille/digest/inventaire.

Aucun champ du manifest n'autorise directement une mutation de l'installation du jeu.

### PM-015 — Confiance et signature

La v1 conserve explicitement séparés :

```text
PackageIdentity
RepositoryMetadata
PackageTrust
PackageSignature
```

Aucune signature ou réputation de repository n'est nécessaire pour valider la structure du manifest. Ces couches pourront être ajoutées plus tard sans modifier la signification de `id`, `version` ou des digests exacts.

## 3. Exemple condensé

```json
{
  "schema": "smml.package-manifest/1",
  "id": "com.example.pallet64",
  "name": "Pallet64 example",
  "version": "0.2.6",
  "authors": ["Example Author"],
  "compatibility": {
    "targets": [
      {
        "steamAppId": 387990,
        "gameVersions": ["1.0.6"],
        "engineBuilds": [889]
      }
    ]
  },
  "dependencies": [],
  "capabilities": {
    "provides": [],
    "requires": []
  },
  "conflicts": {
    "packages": [],
    "capabilities": []
  },
  "loadBefore": [],
  "loadAfter": [],
  "persistenceImpact": "worldContent",
  "artifacts": [],
  "files": []
}
```

Cet exemple illustre le schéma ; il ne revendique pas être le manifest de migration définitif du Pallet64 historique.

## 4. Invariants testables

Une implémentation conforme DOIT au minimum vérifier :

1. `id` est un identifiant lower-case stable conforme au schéma ;
2. `version` est SemVer stricte ;
3. tous les ranges de dépendance/conflit utilisent la grammaire SMML v1 ;
4. aucune dépendance ne vise `id` lui-même ;
5. aucun ID de dépendance n'est dupliqué ;
6. aucune capability `id@version` n'est dupliquée dans une même collection ;
7. aucune capability fournie n'est simultanément conflictuelle au même `id@version` ;
8. `loadBefore` et `loadAfter` n'incluent pas le package courant ;
9. leur intersection est vide ;
10. les chemins `files` sont relatifs et sans collision case-insensitive ;
11. `smml.package.json` n'est pas dans `files` ;
12. chaque entrypoint référence exactement un fichier de l'inventaire ;
13. chaque artefact référence exactement un fichier de l'inventaire ;
14. les IDs et chemins d'artefacts sont uniques ;
15. un target selector matche seulement si toutes ses contraintes présentes sont satisfaites ;
16. plusieurs target selectors sont combinés en OR ;
17. `manifestDigest` et `packageDigest` sont calculés sur les octets, jamais reconstruits depuis un objet JSON parsé.

## 5. Hors périmètre v1

- choix effectif d'une version ou d'un provider ;
- détection de cycles ;
- calcul de l'ordre topologique final ;
- format du Lockfile ;
- politiques de repository, signature et confiance ;
- canonicalisation/reformatage du JSON pour l'identité cryptographique ;
- schéma métier des artefacts référencés ;
- politique complète d'extraction ZIP ;
- racines de package autorisées ;
- signature runtime définitive des entrypoints ;
- mutation filesystem et installation.
