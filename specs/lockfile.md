# SMML Lockfile v1

Statut : **candidate freeze** pour GP1 Foundation.

Identifiant de schéma :

```text
smml.lockfile/1
```

JSON Schema :

```text
urn:smml:schema:lockfile:1
```

## 1. Objet

`Lockfile v1` fige le **résultat exact et explicable** d'une résolution SMML.

Il conserve :

- l'identité du Profile source ;
- la cible de jeu stable effectivement résolue ;
- la version de plateforme ;
- les packages exacts et leurs digests ;
- les artefacts sélectionnés ;
- le Hook Pack, l'API et le SDK sélectionnés ;
- les packages racines ;
- l'ordre final ;
- les providers de capabilities ;
- les edges du graphe et la raison de chaque relation ;
- optionnellement, le fingerprint du contenu final lorsqu'il est disponible.

Le Lockfile n'est ni :

- un Profile ;
- un état filesystem courant ;
- un `StateManifest` ;
- un journal transactionnel ;
- une preuve que le jeu est actuellement conforme à ce lockfile.

## 2. Décisions normatives

### LF-001 — Aucune donnée volatile

Un Lockfile ne contient pas :

- timestamp ;
- transaction ID ;
- chemin local ;
- hostname ;
- ordre de découverte filesystem ;
- identifiant aléatoire.

Avec les mêmes entrées de résolution, un Resolver conforme doit produire la même structure de Lockfile.

### LF-002 — Provenance du Profile

`profile` contient :

```text
id
sha256
```

`sha256` est le `profileDigest` défini par `Profile v1`, calculé sur les octets exacts du fichier utilisé pour cette résolution.

Le Profile n'est pas recopié intégralement dans le Lockfile.

### LF-003 — Cible résolue stable

`target` contient la projection stable nécessaire à la reproductibilité :

```text
steamAppId
gameVersion
engineBuild
steamBuildId
steamBranch
platform
canonicalGameFingerprint
```

`platform` conserve `hostOs`, `gameOs` et `compatibilityLayer.kind`.

Le Lockfile ne conserve pas `installationExactFingerprint`, afin qu'un log ou autre artefact runtime autorisé ne change pas le résultat de résolution.

La cible doit satisfaire le sélecteur `target` du Profile source.

### LF-004 — Version de plateforme

`platformVersion` est la version SemVer exacte de SMML ayant produit la résolution.

Elle participe à la provenance du résultat. Aucun range n'est utilisé ici.

### LF-005 — Packages exacts

Chaque entrée de `packages` contient :

```text
id
version
packageDigest
manifestDigest
persistenceImpact
```

`id + version + packageDigest + manifestDigest` identifie l'artefact package exact retenu.

Deux entrées ne peuvent partager le même `id`.

`packages` est stocké dans l'ordre lexicographique ASCII croissant des IDs afin d'éviter que l'ordre de découverte ne modifie le Lockfile. L'ordre de chargement réel est stocké séparément dans `loadOrder`.

### LF-006 — Artefacts exacts sélectionnés

`artifacts` contient les artefacts machine-readable effectivement utilisés par la résolution/application, par exemple :

```text
smml.hook-pack-manifest/1
smml.contract-descriptor/1
smml.runtime-adapter/1
smml.content-contribution/1
```

Chaque entrée contient :

```text
packageId
artifactId
type
path
sha256
```

La clé `(packageId, artifactId)` est unique.

Le chemin est relatif au package et le hash correspond aux octets exacts de l'artefact distribué.

### LF-007 — Composants de plateforme

`components` identifie explicitement :

```text
hookPack
api
sdk
```

`hookPack` référence un package **et** un artefact présent dans `artifacts` de type :

```text
smml.hook-pack-manifest/1
```

`api` et `sdk` référencent des packages exacts présents dans `packages`.

Cette structure enregistre le rôle effectivement retenu sans ajouter rétroactivement un champ de rôle à `PackageManifest v1`. La v1 peut vérifier la présence exacte du package, mais ne prétend pas encore prouver sémantiquement le rôle API/SDK depuis le manifest : aucun champ de rôle/capability canonique correspondant n'est encore figé. Cette preuve devra être ajoutée lorsque ces rôles seront standardisés.

### LF-008 — Packages racines

`roots` relie les demandes du Profile à leur version résolue :

```text
id
requestedRange
resolvedVersion
```

Chaque root doit exister dans `packages`, `resolvedVersion` doit être exactement la version du package correspondant et doit satisfaire `requestedRange`.

`roots` est trié par ID croissant.

Les composants de plateforme automatiquement sélectionnés n'ont pas à apparaître dans `roots`.

### LF-009 — Ordre final

`loadOrder` contient chaque ID de `packages` exactement une fois.

L'ordre est sémantique et représente le tri topologique final du Resolver.

Chaque edge du graphe doit respecter :

```text
index(from) < index(to)
```

Ainsi, un cycle ou un edge contradictoire avec l'ordre verrouillé rend le Lockfile invalide.

### LF-010 — Providers de capabilities

`capabilityProviders` contient, pour chaque capability verrouillée :

```text
id
version
providers[]
```

Les IDs de providers doivent tous exister dans `packages`.

Une même capability `<id>@<version>` ne peut apparaître qu'une fois. `providers` ne contient pas de doublon et est trié par ID croissant.

Le Lockfile enregistre le résultat exact ; la cardinalité reste une propriété des requirements déclarés dans les manifests consommateurs.

### LF-011 — Edges explicables

Chaque edge contient :

```text
from
to
reason
declaredBy
detail
```

`reason` vaut :

```text
hardDependency
softDependency
capability
loadBefore
loadAfter
```

Orientation canonique :

```text
from -> to
```

signifie toujours : `from` doit précéder `to` dans `loadOrder`.

Règles :

- `hardDependency` / `softDependency` : `from` est la dépendance, `to` est le consommateur, `declaredBy == to` ;
- `capability` : `from` est le provider, `to` est le consommateur, `declaredBy == to` ;
- `loadBefore` : `declaredBy == from` ;
- `loadAfter` : `declaredBy == to`.

`detail` contient :

- `range` pour hard/soft dependency ;
- `capabilityId` + `capabilityVersion` pour capability ;
- aucun champ pour loadBefore/loadAfter.

Les edges sont triés par la clé :

```text
(from, to, reason, declaredBy, detail canonique)
```

Deux edges strictement identiques sont interdits.

Cette représentation permet à `smml explain` de justifier l'ordre et les sélections sans reconstituer les manifests historiques.

### LF-012 — Cohérence capability/edge

Tout edge `capability` doit référencer un `from` présent dans les providers verrouillés pour la capability indiquée.

Un provider verrouillé peut exister sans edge si aucun package chargé ne consomme finalement cette capability, mais le Resolver devrait éviter de conserver des sélections inutiles.

### LF-013 — Fingerprint de contenu final

`finalContentFingerprint` est optionnel dans le schéma GP1 car le Composer n'est pas encore implémenté.

Lorsqu'il est présent, il utilise :

```text
algorithm = smml.content-tree-sha256/1
sha256
```

Il représente le fingerprint du **ManagedOutputSet** final staged, et non le fingerprint exact de l'installation runtime. Le `ManagedOutputSet` est l'ensemble des fichiers réguliers dont les octets finaux sont produits ou sélectionnés par SMML pour ce profil, chemins relatifs à la racine du jeu : fichiers vanilla hookés reconstruits, sorties du Composer et fichiers de package copiés dans l'état géré. Les fichiers baseline inchangés et les artefacts runtime ne sont pas inclus ; un chemin supprimé n'a pas d'entrée. Le hash utilise exactement les records `path + NUL + size + NUL + sha256 + LF` de `smml.content-tree-sha256/1`.

**Gate futur :** un Lockfile utilisé comme artefact final d'un profil appliqué devra contenir ce fingerprint. Le futur `StateManifest` pourra décrire l'inventaire détaillé qui prouve ce `ManagedOutputSet`; GP1 n'en duplique pas encore le contenu dans le Lockfile.

### LF-014 — Sérialisation déterministe

La sémantique ne dépend pas de l'ordre des propriétés JSON. Toutefois, l'écrivain officiel SMML devra utiliser une sérialisation stable : UTF-8 sans BOM, fins de ligne LF et ordre d'objets stable.

La v1 impose déjà un ordre canonique aux collections dont l'ordre n'est pas métier (`packages`, `roots`, `artifacts`, `capabilityProviders`, `edges`). `loadOrder` reste volontairement l'ordre métier résolu.

### LF-015 — Ce qui reste hors Lockfile v1

Sont volontairement hors v1 :

- emplacement des repositories ;
- secrets/tokens ;
- chemins locaux d'installation ;
- timestamps ;
- transaction IDs ;
- signatures/trust ;
- inventaire complet du filesystem actif ;
- Ownership Ledger ;
- State Manifest ;
- snapshots utilisateur.

## 3. Exemple

L'exemple complet et sémantiquement valide de référence est :

```text
examples/lockfile.valid.full-example.json
```

Une variante valide avant finalisation du contenu est également fournie :

```text
examples/lockfile.valid.resolved-only.json
```

## 4. Invariants testables

Un validateur conforme doit notamment refuser :

- packages dupliqués ou non triés ;
- root absent des packages ;
- version root incompatible avec son range ;
- `loadOrder` incomplet, dupliqué ou contenant un ID inconnu ;
- artifact référant un package inconnu ;
- Hook Pack référant un artifact absent ou d'un mauvais type ;
- component API/SDK absent des packages ;
- provider inconnu ou dupliqué ;
- capability dupliquée ;
- edge vers un package inconnu ;
- edge dont `declaredBy` est incohérent avec `reason` ;
- edge contredisant `loadOrder` ;
- edge capability absent de `capabilityProviders` ;
- edges non triés ou dupliqués ;
- champ volatile non prévu grâce à `additionalProperties: false`.

Une validation croisée avec le Profile doit en plus vérifier :

- même `profile.id` ;
- `profile.sha256` égal au digest exact du Profile utilisé ;
- correspondance exacte entre les packages racines du Profile et `roots` ;
- correspondance de la cible ;
- respect des sélections explicites de providers.
