# SMML — GP0.3 — Matrice initiale des hooks candidats

**Build étudiée :** Scrap Mechanic 1.0.6.889  
**Baseline fingerprint :** `6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964`  
**Statut :** analyse statique ; aucun hook n'est encore considéré validé moteur.

## 1. Principes

Un hook candidat n'est retenu que s'il remplit au moins un de ces rôles :

1. charger ou rattacher le runtime SMML ;
2. fournir un contrat impossible à obtenir autrement ;
3. remplacer un patch spécifique déjà nécessaire à un mod existant ;
4. fournir une primitive commune dont plusieurs mods ont besoin.

Le Hook Pack ne doit pas chercher à exposer l'ensemble des callbacks Scrap Mechanic. Le corpus contient 632 scripts Lua, 534 classes, 6 654 méthodes et de très nombreux callbacks moteur ; dupliquer toute cette surface dans l'API créerait une dépendance inutile au vanilla.

## 2. Niveaux de priorité

- **H0 — fondation** : nécessaire pour charger SMML.
- **H1 — migration MVP** : nécessaire pour migrer les mods actuels sans patch spécifique.
- **H2 — plateforme** : utile à court terme, mais non indispensable au premier démarrage.
- **H3 — différé** : ne pas patcher avant apparition d'un besoin concret.

## 3. Matrice

| Priorité | Contrat candidat | Point vanilla observé | Côté | Fréquence | Besoin | Risque | Preuve GP0 requise |
|---|---|---|---|---|---|---|---|
| H0 | `runtime.bootstrap@1` | top-level `SurvivalGame.lua` + lifecycle | shared | chargement | charger le Runtime Adapter | élevé | ordre réel d'évaluation, visibilité globals, idempotence |
| H0 | `game.serverCreated@1` | `SurvivalGame.server_onCreate` | serveur | par création Game | obtenir l'instance serveur et initialiser les services | moyen | nombre d'appels, refresh/reload, host |
| H0 | `game.clientCreated@1` | `SurvivalGame.client_onCreate` | client | par création Game | obtenir l'instance client, réseau et contexte | moyen | host/client distant, reload |
| H0 | `game.serverUnload@1` | `SurvivalGame.server_onUnload` | serveur | rare | cleanup runtime | faible | séquence unload/reload |
| H1 | `carry.resolveInsertTarget@1` | fin/extension de `CarryTool.cl_tryInsert` | client | potentiellement chaque update en carry | remplacer les tables vanilla patchées pour cibles d'insertion custom | élevé | benchmark, ordre vanilla→mods, raycast réutilisé |
| H1/H2 | `carry.beforeServerDrop@1` | `CarryTool.sv_n_dropCarry` avant `Sv_DropCarry` | serveur | action utilisateur | validation autoritaire de placement/support | moyen | placement normal, multishape, carry data, transaction |
| H2 | `game.playerJoined@1` | `SurvivalGame.server_onPlayerJoined` | serveur | connexion | handshake/fingerprint multijoueur | moyen | host + client distant |
| H2 | `game.playerLeft@1` | `SurvivalGame.server_onPlayerLeft` | serveur | déconnexion | cleanup session | faible | déconnexion normale/forcée |
| H2 | `player.serverCreated@1` | `SurvivalPlayer.server_onCreate` | serveur | par joueur | contexte joueur/API | moyen | ordre relatif à `server_onPlayerJoined` |
| H2 | `player.clientCreated@1` | `SurvivalPlayer.client_onCreate` | client | par joueur | contexte joueur local | moyen | host/client distant |
| H2/H3 | `carry.beforeReceiveRelay@1` | `CarryTool.sv_n_sendItem` | serveur | action utilisateur | politique centrale facultative avant `sv_e_receiveItem` | moyen | vérifier absence de régression vanilla |
| H3 | `player.inventoryChanged@1` | `SurvivalPlayer.server_onInventoryChanges` | serveur | potentiellement fréquent | notification d'inventaire joueur | élevé | benchmark ; ce hook ne couvre pas tous les containers |
| H3 | `game.serverFixedUpdate@1` | `SurvivalGame.server_onFixedUpdate` | serveur | chaque tick | scheduler/queue SDK | élevé | coût à vide mesuré |
| H3 | `game.clientFixedUpdate@1` | `SurvivalGame.client_onFixedUpdate` | client | chaque tick | scheduler client | élevé | coût à vide mesuré |
| H3 | `recipes.beforeLoad@1` | `SurvivalGame.loadCraftingRecipes` | shared | chargement/refresh | extensions dynamiques de recettes | moyen | à éviter si Composer suffisant |
| H3 | `recipes.unlocked@1` | `RecipeManager.sv_unlockRecipe` | serveur | événementiel | observation/extension unlock | faible | besoin réel à confirmer |

## 4. Décision initiale sur les recettes

Le chargement vanilla lit d'abord :

```text
$SURVIVAL_DATA/CraftingRecipes/craftbot/craftbot.json
```

puis ajoute plusieurs sets fixes et appelle `LoadCraftingRecipes(recipeSets)`.

`craftbot.json` est lui-même une table `nom_du_set -> chemin` et `LoadCraftingRecipes` traite automatiquement les sets dont le nom commence par `craftbot_`.

Conséquence : **l'ajout de recettes ne nécessite pas nécessairement de hook runtime**. Le Content Composer peut générer un `craftbot.json` résolu et les fichiers de recettes correspondants.

`recipes.beforeLoad@1` reste donc H3 tant qu'un besoin dynamique concret n'est pas démontré.

## 5. CarryTool — frontière recommandée

### 5.1 Insertion

`CarryTool.cl_tryInsert` effectue déjà :

1. un raycast local à 7,5 ;
2. la résolution des cibles vanilla ;
3. la vérification du type de ressource ;
4. l'affichage de l'interaction ;
5. l'envoi vers `sv_n_sendItem`.

Le hook le moins intrusif serait ajouté **après les cibles vanilla et avant le `return false` final**, en réutilisant le résultat du raycast déjà calculé.

Le runtime pourrait alors exposer un contexte interne normalisé :

```text
CarryInsertContext
  player/tool
  carryUuid
  carryColor
  raycastResult
  targetShape / targetHarvestable
  primaryState
```

Le contrat public ne doit pas dépendre de la table locale `ContainerInsertTargets` ni des paramètres bruts de `CarryTool.lua`.

### 5.2 Drop/placement

Le client obtient le placement par :

```text
sm.localPlayer.getConstructionPlacement()
```

puis `sv_n_dropCarry` ajoute `params.player` et délègue à la fonction globale `Sv_DropCarry`.

`Sv_DropCarry` dépense l'objet puis appelle directement `sm.shape.createPart` ou `sm.creation.buildMultiShape`.

Pour une future règle structurelle de palettes, le point serveur pertinent est donc avant l'appel à `Sv_DropCarry`, pas un hook générique après création.

## 6. Ce qui ne doit pas devenir un hook générique en v1

### Shape created / interactable created

L'analyse statique ne montre pas un point Lua unique qui centralise toutes les créations de Shapes/interactables. Ajouter un contrat `shape.created` en patchant de nombreux call-sites serait contraire à l'objectif d'un Hook Pack minimal.

**Décision : différer.**

### Tous les callbacks moteur

Le corpus contient notamment :

- `server_onCreate` : 340 implémentations ;
- `client_onCreate` : 294 ;
- `server_onFixedUpdate` : 213 ;
- `client_onClientDataUpdate` : 173 ;
- `client_onUpdate` : 166 ;
- `client_onDestroy` : 140.

Ces callbacks restent accessibles aux scripts propres des contenus moddées. Il n'est pas nécessaire que SMML les réexporte tous.

## 7. Probes runtime nécessaires avant gel du Hook Pack

### P-HOOK-001 — visibilité globale

Déterminer si un runtime défini lors du chargement de `SurvivalGame.lua` est visible depuis :

- `SurvivalGame` ;
- `SurvivalPlayer` ;
- `CarryTool` ;
- un ShapeClass ;
- un Scriptable Object ;
- serveur et client séparément.

### P-HOOK-002 — ordre de chargement

Tracer :

```text
top-level Lua
server/client_onCreate
player create
world lifecycle
refresh
unload
reload
```

### P-HOOK-003 — idempotence

Appeler volontairement le loader depuis plusieurs points et garantir une initialisation unique.

### P-HOOK-004 — erreur handler

Tester `xpcall`, traceback et continuation contrôlée.

### P-HOOK-005 — Carry insert

Mesurer le coût d'un hook vide dans `cl_tryInsert` et tester :

- cible vanilla ;
- cible custom ;
- aucun subscriber ;
- plusieurs subscribers ;
- client distant.

### P-HOOK-006 — Carry server drop

Valider le contrat cancellable avant `Sv_DropCarry` sans consommation ni duplication lorsque l'opération est refusée.

## 8. Critère de sortie GP0.3

GP0.3 pourra être considéré terminé lorsque chaque hook du premier Hook Pack possède :

- un besoin documenté ;
- une ancre identifiée sur 1.0.6.889 ;
- une fréquence connue ;
- une politique de composition ;
- un contrat interne distinct des paramètres vanilla ;
- un test statique ;
- un probe moteur réussi ;
- un test de non-régression sans mod abonné.
