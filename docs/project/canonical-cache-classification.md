# Classification canonique du cache — GP1

## Objet

Cette note formalise la révision de `smml.canonical-game-policy/1` vers `smml.canonical-game-policy/2` après une inspection réelle de Scrap Mechanic `1.0.6.889` ayant montré un drift de `Cache/` sans drift des cibles critiques observées.

## FACT — baseline GP0 B0

Le corpus GP0 B0 contient :

```text
61 370 fichiers
20 596 856 244 octets
exact = 6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964
```

Sous `Cache/` :

```text
20 119 fichiers
5 254 624 637 octets
root fp = affd1530a458ac21782eabca281426fadf38b5de9a43f76ad1620462ca1d8cf1
```

Les 20 119 fichiers de `Cache/` portent tous le hint GP0 :

```text
reference_only:generated_cache
```

Ce hint est une donnée de capture/advisory, pas une propriété moteur universelle.

## FACT — B0 -> B1

B1 ajoute un seul fichier `Logs/game-...log`, crée des répertoires runtime, et ne modifie/supprime aucun fichier B0 existant.

Le fingerprint `Cache/` reste strictement identique :

```text
affd1530a458ac21782eabca281426fadf38b5de9a43f76ad1620462ca1d8cf1
```

## FACT — observation réelle du 2026-09-30 sous policy v1

L'Inspector a produit :

```text
exact files      61 397
exact bytes      20 617 246 687
canonical v1     61 385 fichiers
canonical bytes  20 600 159 517
canonical v1 fp  481304077a026cb62c1f0a8a725519afe839d39ef11d3d6223d56821f08fb8d3
```

Par rapport à B0, le canonique v1 contient donc :

```text
+15 fichiers
+3 303 273 octets
```

Le fingerprint racine `Cache/` a changé :

```text
B0      affd1530a458ac21782eabca281426fadf38b5de9a43f76ad1620462ca1d8cf1
actuel  32c35f46162adb2d6da969d33eb71fda542136033b6bac58a9eaa022cce6d6aa
```

Les roots observées `ChallengeData`, `Data`, `Release`, `Survival` et les cinq targets critiques de l'ancienne inspection conservent les valeurs GP0. L'ancienne inspection ne sortait toutefois pas l'inventaire complet ni les roots `Challenges` / `ParticleEditorData`; elle ne permet donc pas d'identifier honnêtement les 15 chemins exacts.

## INFERENCE

Le drift observé est compatible avec des artefacts rebuildables dans `Cache/`. La combinaison suivante constitue une preuve suffisante pour faire évoluer l'identité canonique :

- tous les fichiers B0 sous `Cache/` sont classés `generated_cache` par la capture ;
- B0/B1 ont le même `Cache/` ;
- une exécution ultérieure fait dériver `Cache/` sans dériver les targets critiques connues ;
- le projet traite déjà `Cache/Bundle/core_data.cbo` par invalidation ciblée dans les probes GP0.

Cette conclusion ne signifie pas que tout fichier futur nommé `Cache/*` est sans importance pour la compatibilité. Les targets critiques restent vérifiées séparément.

## DESIGN DECISION — policy v2

```text
smml.canonical-game-policy/2

exclude Cache/
exclude Logs/
include everything else
```

Classification :

```text
Cache/  -> rebuildable-cache
Logs/   -> runtime-ephemeral
```

La baseline B0 recalculée donne :

```text
41 251 fichiers
15 342 231 607 octets
f8356e5f0b660320bdcd196bc553114d688aeff43f20872438cbac1e1bc9668c
```

B1 produit la même valeur parce que son unique delta fichier est sous `Logs/` et que `Cache/` est inchangé.

## Cibles strictes malgré l'exclusion canonique

`Cache/Bundle/core_data.cbo` reste dans `targetFingerprints` :

```text
682efa4378e69f1a711e1d2147c302fbdd0dc8035f841c948d50c50964181351
```

L'exclusion de `Cache/` du canonique ne remplace donc jamais les preconditions de Hook Pack ou de transaction.

## Vérification de l'installation actuelle

Le nouvel Inspector peut produire dans la même inspection :

```text
--inventory-output artifacts/game-target-inventory.json.gz
--cache-diff-output artifacts/cache-diff.json
--require-known-canonical
```

Le diff contient la liste exacte des `added`, `removed` et `modified` sous `Cache/` par rapport à B0.

**État de preuve au moment de ce commit :** B0/B1 sont vérifiés avec policy v2. L'installation actuelle n'est pas encore vérifiée sous policy v2 dans l'environnement de construction car seul son ancien `game-target.json`, sans inventaire fichier par fichier, a été fourni. Le CLI est désormais capable de produire cette preuve sans ambiguïté lors du prochain run local.
