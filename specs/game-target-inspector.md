# GameTargetInspector — spécification v1

**Plan d'inspection :** `smml.game-target-inspection-plan/1`  
**Sortie :** `smml.game-target/1`  
**Statut :** GP1 / v1 — candidate freeze  
**Implémentation de référence :** `reference/python/smml_reference/game_target_inspector.py`

## 1. Objet

`GameTargetInspector` transforme une installation Scrap Mechanic observée en un `GameTargetIdentity` déterministe et vérifiable.

Il ne sélectionne pas de Hook Pack et n'autorise aucune mutation.

Pipeline v1 :

```text
trusted game root
+ Steam appmanifest
+ versioned inspection plan
+ canonical game policy
        ↓
filesystem inventory (no-follow / fail-closed)
        ↓
stable exact-byte hashing
        ↓
second metadata pass
        ↓
exact / canonical / root / target fingerprints
        ↓
GameTargetIdentity
```

## 2. Sources d'autorité

### GTI-I-001 — Steam AppID / build / branche

L'Inspector DOIT obtenir `steamAppId` et `steamBuildId` depuis le `appmanifest_<appid>.acf` Steam correspondant à l'installation.

La branche est :

- la `betakey` explicitement présente lorsqu'elle existe ;
- `public` lorsqu'aucune beta n'est déclarée.

L'Inspector DOIT vérifier que `installdir` correspond exactement au basename du game root.

### GTI-I-002 — gameVersion / engineBuild

La v1 NE DOIT PAS deviner `gameVersion` ou `engineBuild` depuis un nom de fichier, un timestamp, une chaîne trouvée arbitrairement dans un binaire ou une version supposée « latest ».

Ces valeurs proviennent du `GameTargetInspectionPlan` versionné, indexé par :

```text
steamBuildId + steamBranch
```

Un build Steam absent du plan produit `GTI_UNKNOWN_STEAM_BUILD`.

Cette décision rend l'ajout d'une nouvelle build explicite et auditable.

### GTI-I-003 — plateforme

`hostOs` et `hostArch` sont observés sur le host.

`gameOs` et `gameArch` proviennent du plan de build connu.

Si `hostOs != gameOs`, la couche de compatibilité DOIT être fournie explicitement (`proton`, `wine` ou `other`). L'Inspector NE DOIT PAS conclure silencieusement « Proton » uniquement parce que le host est Linux.

La version de la couche est optionnelle lorsqu'elle n'est pas prouvée.

## 3. Plan d'inspection

Le format `smml.game-target-inspection-plan/1` contient :

```text
steamAppId
canonicalPolicy
builds[]
  steamBuildId
  steamBranch
  gameVersion
  engineBuild
  gameOs
  gameArch?
  rootFingerprints[]
  targetFingerprints[]
```

Les chemins utilisent `PathPolicy v1` et doivent être uniques selon `PortableCollisionKey`.

Le plan n'embarque aucun hash attendu de baseline. Son rôle est de décrire **quoi observer** et comment nommer une build Steam déjà connue ; l'identité observée reste calculée à partir des octets locaux.

## 4. Inspection filesystem

### GTI-I-004 — racine de confiance

La racine doit :

- exister ;
- être un répertoire ;
- ne pas être un symlink ;
- ne pas être un reparse point.

Les erreurs remontent fail-closed.

### GTI-I-005 — inventaire

Tous les objets sous le game root sont inspectés sans intention de mutation.

La v1 accepte uniquement :

```text
directory
regular-file
```

Un symlink ou reparse point produit l'erreur PathPolicy correspondante. Un autre type d'objet est rejeté.

Tous les chemins observés DOIVENT être valides selon `PathPolicy v1`. Toute collision `PortableCollisionKey` est rejetée.

### GTI-I-006 — acquisition stable d'un fichier

Pour chaque fichier régulier :

1. `lstat` avant ouverture ;
2. ouverture read-only, avec `O_NOFOLLOW` lorsqu'il est disponible ;
3. `fstat` avant lecture ;
4. hash SHA-256 des octets exacts ;
5. `fstat` après lecture ;
6. `lstat` du chemin après fermeture.

Le type, l'identité filesystem, la taille, `mtime` et `ctime` observés doivent rester stables. La quantité d'octets lue doit être égale à la taille observée.

Toute divergence produit :

```text
GTI_FILESYSTEM_CHANGED
```

### GTI-I-007 — stabilité de l'inventaire

Après le hashing, une seconde passe metadata DOIT vérifier que :

- la racine est inchangée ;
- aucun chemin n'a été ajouté ou supprimé ;
- aucun objet n'a changé de type ou de signature metadata.

Un jeu en cours d'écriture peut donc faire échouer l'inspection. C'est volontaire : la v1 privilégie un état fermé et stable.

## 5. Fingerprints

L'Inspector DOIT réutiliser `Hashing v1` sans variante locale.

### Exact

```text
installationExactFingerprint
```

porte sur tous les fichiers réguliers observés sous le game root.

### Canonique

```text
canonicalGameFingerprint
```

porte sur le même inventaire après application exclusive de `smml.canonical-game-policy/1`.

Aucune exclusion implicite n'est autorisée.

### Racines

Chaque `rootFingerprints[]` du plan DOIT désigner un répertoire existant avec casse exacte.

Le hash utilise `smml.content-tree-sha256/1` en conservant les chemins relatifs au game root.

### Cibles

Chaque `targetFingerprints[]` du plan DOIT désigner un fichier régulier existant avec casse exacte.

Le hash est le `sha256` exact du fichier déjà acquis dans l'inventaire. Le fichier n'est pas relu avec une primitive différente.

## 6. Déterminisme

Pour une installation byte-identical, un même appmanifest, un même plan, une même politique canonique et les mêmes paramètres plateforme, la sortie JSON logique DOIT être identique.

Le document ne contient pas :

```text
timestamp
chemin local du jeu
chemin local Steam
nom d'utilisateur
```

Les listes de roots/targets sont émises dans l'ordre `PortableCollisionKey` puis UTF-8 exact.

## 7. Frontière de sécurité

Un `GameTargetIdentity` produit par l'Inspector n'est **jamais** une autorisation de mutation.

Le futur pipeline reste :

```text
GameTargetInspector
→ HookPack selection
→ target beforeHash validation
→ anchors / structural validation
→ TransactionJournal
→ TransactionEngine
```

Le `TransactionEngine` doit réinspecter les préconditions immédiatement avant mutation.

L'inspection v1 ne prétend donc pas résoudre à elle seule une attaque TOCTOU située après la fin de l'inspection.

## 8. Portabilité du backend de référence

L'implémentation Python utilise `O_NOFOLLOW` lorsque le host l'expose et effectue des contrôles `lstat/fstat` avant/après lecture.

Sur Windows, la classification des reparse points utilise `st_file_attributes` lorsqu'elle est fournie par Python. Une future implémentation de production devra utiliser les primitives handle-relative/no-follow spécifiques à chaque OS ; cette exigence reste portée par `PathPolicy v1`.

## 9. Codes d'erreur spécifiques v1

En plus des codes `PathPolicy` :

```text
GTI_PLAN_INVALID
GTI_JSON_INVALID
GTI_APPMANIFEST_NOT_FOUND
GTI_APPMANIFEST_INVALID
GTI_APPID_MISMATCH
GTI_INSTALLDIR_MISMATCH
GTI_UNKNOWN_STEAM_BUILD
GTI_BRANCH_MISMATCH
GTI_UNSUPPORTED_HOST
GTI_COMPATIBILITY_LAYER_REQUIRED
GTI_COMPATIBILITY_LAYER_INVALID
GTI_FILESYSTEM_CHANGED
GTI_REQUIRED_ROOT_MISSING
GTI_REQUIRED_TARGET_MISSING
GTI_OUTPUT_INSIDE_GAME_ROOT
```

## 10. Hors périmètre v1

- découverte d'installations Steam dans toutes les bibliothèques ;
- interrogation réseau de Steam ;
- reconnaissance heuristique d'une build inconnue ;
- cache incrémental de hashes ;
- parallélisation du hashing ;
- création/gestion du Baseline Vault ;
- sélection finale du Hook Pack ;
- mutation de l'installation ;
- backend filesystem de production Windows/POSIX par handles durcis.
