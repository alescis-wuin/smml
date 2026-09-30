# SMML HookPackManifest v1

Statut : **candidate freeze** pour GP1 Foundation.

Identifiant de schéma :

```text
smml.hook-pack-manifest/1
```

JSON Schema :

```text
urn:smml:schema:hook-pack-manifest:1
```

## 1. Objet

`HookPackManifest v1` décrit les données spécifiques à une ou plusieurs cibles Scrap Mechanic qu'un **Hook Patcher Engine générique** peut utiliser pour produire des hooks déterministes et vérifiables.

Le manifest relie explicitement :

```text
GameTargetIdentity
  -> baseline file preconditions
  -> anchors
  -> transformations déclaratives
  -> Runtime Adapter
  -> ContractDescriptor
  -> cache consequences
```

Un Hook Pack ne constitue pas :

- un moteur de patch ;
- une autorisation d'écriture directe ;
- un lockfile ;
- un journal transactionnel ;
- un contrat public pour les mods ;
- un mécanisme RPC ;
- un Content Composer.

Le Hook Patcher produit des sorties **staged**. Le `TransactionEngine` reste l'unique composant chargé de convertir ces sorties en mutations durables du jeu.

## 2. Décisions normatives

### HPM-001 — Identité du Hook Pack

`HookPackManifest v1` est un artefact référencé par `PackageManifest` avec :

```text
type = smml.hook-pack-manifest/1
```

Il ne duplique pas un `packageId` ou une version de package dans son contenu.

Son identité exacte est dérivée du contexte package :

```text
package id
+ package version
+ packageDigest
+ manifestDigest
+ artifact id/path/digest
```

Plusieurs manifests de Hook Pack peuvent donc être distribués par un même package si plusieurs variantes explicites sont nécessaires.

### HPM-002 — Sélection par preuves multiples

`targets` contient une ou plusieurs identités de cible exactes. Elles sont combinées en **OR**.

Chaque cible v1 exige :

```text
steamAppId
gameVersion
engineBuild
steamBuildId
steamBranch
canonicalGameFingerprint
```

Les contraintes suivantes sont optionnelles lorsqu'un Hook Pack dépend réellement de la plateforme :

```text
hostOs
gameOs
compatibilityLayer
```

Un match `targets` n'autorise pas encore le patch.

L'applicabilité complète exige :

```text
metadata cible
+
fingerprint canonique
+
hash baseline de chaque fichier cible
+
anchors exactement résolus
+
validation structurelle des transformations
```

La sélection par `gameVersion` ou `engineBuild` seul est interdite.

### HPM-003 — Preconditions sur la baseline

`targetFiles` décrit les fichiers vanilla que le Hook Pack sait transformer.

Chaque entrée contient :

```text
id
path
acceptedBaselineSha256[]
textPolicy
```

`acceptedBaselineSha256` est évalué sur les octets de la **baseline immuable suivie par SMML**, pas sur un fichier actuellement patché dans l'installation.

Plusieurs hashes ne signifient jamais « tolérer n'importe quelle variante ». Chaque variante supportée doit être listée explicitement.

Le moteur doit refuser :

- hash absent de la liste ;
- fichier absent ;
- objet autre qu'un fichier régulier ;
- symlink/reparse point inattendu ;
- chemin sortant de la racine gérée.

`PathPolicy` et le `TransactionEngine` fourniront les contrôles filesystem complets. Le Hook Pack ne peut pas les désactiver.

### HPM-004 — Politique texte v1

Les fichiers hookés en v1 sont des fichiers texte Lua :

```text
encoding = utf-8
bomPolicy = forbid
newlinePolicy = preserve
```

Le moteur peut normaliser temporairement LF/CRLF dans sa représentation logique pour parser/localiser, mais doit réémettre le style de fin de ligne homogène observé dans la baseline.

Un fichier à fins de ligne mixtes ou non décodable selon la politique déclarée doit être refusé plutôt que normalisé silencieusement.

### HPM-005 — Anchors

Deux formes d'anchor sont définies en v1.

#### `exact-text`

```json
{
  "id": "server-on-create-header",
  "kind": "exact-text",
  "text": "function SurvivalGame.server_onCreate( self )\n",
  "cardinality": "exactly-one"
}
```

L'anchor est recherché dans la représentation texte logique du fichier.

#### `lua-function`

```json
{
  "id": "drop-function",
  "kind": "lua-function",
  "symbol": "CarryTool.sv_n_dropCarry",
  "cardinality": "exactly-one"
}
```

Cette forme exige un parseur/tokenizer Lua capable d'identifier la fonction. Une implémentation ne doit pas la dégrader silencieusement en regex ou recherche approximative.

Pour toute anchor v1 :

```text
0 match   -> FAIL CLOSED
1 match   -> acceptable
>1 match  -> FAIL CLOSED
```

Le fait qu'un hash baseline soit reconnu ne dispense jamais de résoudre les anchors attendus.

### HPM-006 — Transformations déclaratives

Les transformations v1 sont :

```text
insert-before
insert-after
replace-region
wrap-prefix
wrap-postfix
conditional-short-circuit
```

Elles sont exécutées dans l'ordre explicite `sequence = 0..N-1` au sein d'un hook.

Le contenu injecté/remplaçant n'est pas embarqué dans le manifest. Il est référencé par :

```text
contentArtifactId
```

qui doit désigner un artefact package de type :

```text
smml.hook-patch-fragment/1
```

Ainsi, les octets de chaque fragment sont couverts par l'inventaire/digest du package.

#### Insertions

`insert-before` et `insert-after` référencent une anchor unique.

#### Remplacement borné

`replace-region` référence :

```text
startAnchorId
endAnchorId
includeStart
includeEnd
```

Les deux anchors doivent être distinctes. Le moteur doit démontrer un ordre structurel non ambigu avant remplacement.

#### Transformations de fonction

```text
wrap-prefix
wrap-postfix
conditional-short-circuit
```

exigent une anchor `lua-function`.

`wrap-prefix` insère au début logique du corps de fonction.

`wrap-postfix` insère avant la fin lexicale de la fonction ; v1 ne prétend pas intercepter automatiquement tous les `return` anticipés.

`conditional-short-circuit` insère au début logique du corps un fragment pouvant terminer explicitement l'appel.

### HPM-007 — Adapter et contrat stable

Chaque hook possède également un `sequence` global. Les hooks sont appliqués dans l’ordre exact `0..N-1`, indépendamment de leur ordre de découverte ou de leur position accidentelle dans une structure interne.

Chaque hook référence :

```text
contract.contractId
contract.version
contract.descriptorArtifactId
adapterId
```

`descriptorArtifactId` doit désigner :

```text
smml.contract-descriptor/1
```

L'adapter référencé par `adapterId` doit désigner un artefact :

```text
smml.runtime-adapter/1
```

Lorsque le contenu du `ContractDescriptor` est disponible, son `contractId@version` doit correspondre exactement à la référence du hook.

Le mod ne voit jamais :

```text
targetFileId
path
anchor
fragment
transformation
```

Il dépend uniquement du contrat stable, par exemple :

```text
game.serverCreated@1
```

### HPM-008 — Idempotence et vérification

Chaque hook possède deux marqueurs exacts :

```text
verification.beginMarker
verification.endMarker
```

Ils doivent être distincts et uniques dans le Hook Pack.

Après transformation staged, chacun doit apparaître exactement une fois, dans l'ordre début puis fin.

Un Hook Patcher conforme ne doit jamais dupliquer une injection déjà reconnue. Cependant, l'installation/reconfiguration normale de SMML doit préférer :

```text
baseline
+ Hook Pack sélectionné
-> nouvelle sortie staged
```

plutôt qu'une accumulation de patchs différentiels sur le fichier géré courant.

### HPM-009 — Un Hook Pack sélectionné est appliqué comme une unité v1

La v1 ne définit pas d'activation conditionnelle individuelle des hooks.

Si un `HookPackManifest` est sélectionné, tous les éléments de `hooks` sont planifiés.

Cette règle rend la sortie reproductible et évite qu'un même Hook Pack produise implicitement plusieurs surfaces vanilla selon l'ordre des mods.

Un besoin de variantes doit utiliser des Hook Packs explicites distincts jusqu'à définition éventuelle d'un modèle de features versionné.

### HPM-010 — Conséquences de cache

`cacheConsequences` ne peut déclarer en v1 que :

```text
kind = invalidate-file
trigger = hook-pack-change
path = chemin exact relatif au game root
```

Aucun glob, purge de dossier ou « clear all caches » n'est défini.

L'invalidation n'est exécutée que si la sortie du Hook Pack modifie effectivement l'état géré.

Un cache absent est un no-op. Un symlink/reparse point inattendu reste une erreur de sécurité.

La présence d'une conséquence dans le manifest n'autorise pas le Hook Patcher à supprimer lui-même le fichier : la mutation reste orchestrée par le `TransactionEngine`.

### HPM-011 — Pas de `afterHash` auto-déclaré

Le manifest n'impose pas de hash de sortie finale.

La sortie exacte dépend des fragments et de leur composition déterministe. Le Hook Patcher doit :

```text
baseline bytes
-> transforms
-> structural verification
-> staged bytes
-> compute SHA-256
```

Le `TransactionJournal` enregistre ensuite ce hash staged comme `after.sha256` de la mutation.

Cela évite un deuxième système d'identité cryptographique et conserve le journal comme preuve de l'opération réellement planifiée.

### HPM-012 — Frontière transactionnelle

Le Hook Patcher Engine ne doit pas écrire directement dans l'installation finale.

Pipeline :

```text
GameTargetInspector
-> HookPack selection
-> baseline preconditions
-> anchor resolution
-> transform in staging
-> verify markers/structure
-> compute staged hash
-> TransactionJournal PREPARED
-> TransactionEngine commit
-> targeted cache consequences
-> final verification
```

Toute incompatibilité avant commit doit laisser l'installation inchangée.

### HPM-013 — Ressources runtime non figées en v1

Le handoff établit que les canaux `setClientData` 3 et 4 sont utilisables sur la build testée, mais la politique exacte d'allocation reste ouverte.

`HookPackManifest v1` ne crée donc pas encore de champ public `clientDataChannel` ou équivalent. Cette allocation devra être modélisée séparément comme capability/ressource lorsque sa politique sera définie.

## 3. Exemple de référence 1.0.6.889

L'exemple fourni avec le package utilise des faits GP0 établis :

```text
Steam AppID       387990
gameVersion       1.0.6
engineBuild       889
Steam build       25442087
branch            public
canonical fp      6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964
SurvivalGame.lua  934beb15dff2f34638128a56aa1be8586e363bc1a5d564698e9b8f09bf9d35c4
cache             Cache/Bundle/core_data.cbo
```

L'anchor `SurvivalGame.server_onCreate` utilisé par l'exemple a déjà été employé par les probes GP0. Le fragment et l'adapter restent des références d'artefacts de démonstration : ce package Foundation ne constitue pas encore le Hook Pack de production.

## 4. Invariants testables

Une implémentation conforme doit au minimum vérifier :

1. au moins une cible exacte est déclarée ;
2. chaque cible contient métadonnées + fingerprint canonique ;
3. les cibles dupliquées sont rejetées ;
4. les IDs de `targetFiles`, adapters, hooks et cache consequences sont uniques ;
5. les chemins de fichiers cibles n'ont aucune collision case-insensitive ;
6. les chemins de cache n'ont aucune collision case-insensitive ;
7. un chemin de cache ne peut pas être aussi un fichier cible ;
8. chaque hook référence un `targetFileId` existant ;
9. chaque hook référence un `adapterId` existant ;
10. les séquences de hooks sont exactement `0..N-1` ;
11. les IDs d'anchors sont uniques dans le hook ;
12. les séquences de transformations sont exactement `0..N-1` ;
13. chaque transformation référence des anchors existantes ;
14. `replace-region` utilise deux anchors distinctes ;
15. les transformations de fonction utilisent une anchor `lua-function` ;
16. les marqueurs begin/end sont distincts et globalement uniques ;
17. chaque adapter artifact existe dans le PackageManifest et a le type attendu ;
18. chaque ContractDescriptor référencé existe et a le type attendu ;
19. chaque fragment de transformation existe et a le type attendu ;
20. si le descriptor est chargé, sa clé correspond exactement au contrat référencé ;
21. un target selector ne matche qu'une `GameTargetIdentity` exacte sur tous les champs présents ;
22. tous les `targetFiles` doivent matcher leur baseline hash avant patch ;
23. chaque anchor `exact-text` doit matcher exactement une fois ;
24. zéro ou plusieurs matches bloquent le patch ;
25. aucune sélection ne peut reposer uniquement sur un numéro de version.

## 5. Hors périmètre v1

- implémentation du parser/tokenizer Lua ;
- représentation AST définitive ;
- format interne des fragments de patch au-delà de leurs octets UTF-8 ;
- activation conditionnelle hook par hook ;
- négociation automatique entre plusieurs Hook Packs compatibles ;
- allocation des canaux `setClientData` ;
- network bindings / ACLs ;
- budgets de performance des hot paths ;
- format des preuves runtime historiques ;
- stratégie de signature/confiance des Hook Packs ;
- `PathPolicy` complet ;
- primitives OS de remplacement atomique/fsync/locks.
