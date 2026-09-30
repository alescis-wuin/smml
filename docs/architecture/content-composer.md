# SMML — GP0.4 — Cartographie initiale du Content Composer

**Build étudiée :** Scrap Mechanic 1.0.6.889  
**Baseline fingerprint :** `6538e09bfcc535534cced2d9c4174d235605399f3ce3dbcf4fd752868c223964`  
**Statut :** cartographie statique initiale.

## 1. Conclusion principale

Scrap Mechanic ne possède pas un unique registre de contenu. Survival référence plusieurs familles de catalogues racines, chacune ayant sa propre structure et ses propres identités.

Le Content Composer doit donc être un **framework d'adaptateurs de registres**, pas un mergeur JSON générique.

## 2. Registres racines Survival observés

| Domaine | Registre | Entrées racines | Forme |
|---|---|---:|---|
| Shapes | `Survival/Objects/Database/shapesets.json` | 75 | liste de chemins |
| Effects | `Survival/Effects/Database/effectsets.json` | 145 | objets `{path, showInEditor...}` |
| Terrain assets | `Survival/Terrain/Database/assetsets.json` | 58 | objets `{assetSet, categories...}` |
| Kinematics | `Survival/Kinematics/Database/kinematicsets.json` | 23 | objets `{name, categories...}` |
| Harvestables | `Survival/Harvestables/Database/harvestablesets.json` | 20 | objets `{name, categories...}` |
| Decals | `Survival/Decals/decalsets.json` | 13 | objets `{set, category...}` |
| Voxel materials | `Survival/Terrain/Materials/voxel_materialset_list.json` | 7 | objets `{materialSet, name}` |
| Characters | `Survival/Character/charactersets.json` | 6 | liste de chemins |
| Scriptable Objects | `Survival/ScriptableObjects/scriptableObjectSets.sobdb` | 6 | objets `{scriptableObjectSet}` |
| Tools | `Survival/Tools/toolsets.json` | 5 | liste de chemins |
| Ground materials | `Survival/Terrain/Materials/gnd_materialset_list.json` | 3 | objets `{materialSet, name}` |
| Projectiles | `Survival/Projectiles/projectilesets.json` | 3 | liste de chemins |

D'autres familles existent dans `Data`, `ChallengeData` et les Example Mods ; elles serviront de références pour étendre les adaptateurs.

## 3. Identités de niveau contenu

### 3.1 Shapes

Un `.shapeset` contient notamment :

```text
partList
blockList
wedgeList
```

Les objets portent un `uuid`.

Dans les 75 sets enregistrés par Survival :

- 1 282 définitions Shape observées ;
- 1 276 UUID distincts ;
- 6 UUID apparaissent plusieurs fois.

Plusieurs doublons sont strictement identiques. Au moins un doublon vanilla est **non identique** : l'UUID `be29592a-ef58-4b1d-b18c-895023abd27f` apparaît dans deux sets avec une différence de `physicsMaterial` (`Mechanical` vs `Metal`).

Conséquence importante :

> le Composer ne peut pas appliquer la règle naïve « UUID dupliqué = erreur » à la baseline vanilla.

Politique proposée :

1. préserver exactement l'ordre et les doublons du baseline ;
2. reconnaître les doublons vanilla comme faits de baseline ;
3. interdire par défaut qu'un mod introduise un UUID déjà possédé par une autre contribution ;
4. n'autoriser un override que via une politique explicite et testée ;
5. conserver la provenance de chaque définition.

Le comportement moteur exact du doublon non identique doit être testé avant de définir une sémantique d'override SMML.

### 3.2 Scriptable Objects

Les `.sobset` observés contiennent :

```text
scriptableObjectList[]
  filename
  classname
  uuid
```

L'UUID constitue une identité forte candidate.

Dans les sets Survival enregistrés observés : 111 UUID, sans collision.

### 3.3 Harvestables

Les `.harvestableset` contiennent `harvestableList[]` avec UUID.

Le registre racine ajoute aussi des catégories.

Politique candidate : identité de définition = UUID ; identité d'inscription du set = chemin logique du set + métadonnées de registre.

### 3.4 Kinematics

Les `.kinematicset` contiennent `kinematicList[]` avec UUID.

Une référence du registre utilise `Mechanical.kinematicset` tandis que le fichier capturé est `mechanical.kinematicset`. Le moteur fonctionne donc dans un environnement où cette différence de casse est tolérée.

SMML doit :

- conserver l'orthographe vanilla dans les fichiers générés ;
- détecter les collisions case-insensitive pour compatibilité Windows/Proton ;
- ne pas « corriger » silencieusement le vanilla.

### 3.5 Terrain Assets

Les `.assetset` contiennent notamment `assetListRenderable[]` avec UUID.

Les 58 sets Survival observés regroupent 866 UUID uniques sans collision dans la passe actuelle.

### 3.6 Projectiles

Les `.projectileset` utilisent `projectiles[]` avec `uuid` et `name`.

L'UUID doit être considéré comme identité forte du projectile.

### 3.7 Characters

Les Character Sets contiennent `characters[]` avec UUID.

69 UUID distincts ont été observés dans les sets enregistrés Survival, sans collision lors de cette analyse.

### 3.8 Tools

Les Tool Sets contiennent `toolList[]` avec UUID.

26 UUID distincts observés, sans collision lors de cette analyse.

### 3.9 Effects

Un `.effectset` est différent : sa racine est une table dont les **clés sont directement les noms d'effets**.

Le vanilla contient :

- des noms d'effets présents dans plusieurs sets ;
- deux chemins d'effectset eux-mêmes répétés dans le registre Survival (`claygun.effectset`, `excavation.effectset`).

Il ne faut donc pas supposer immédiatement que le nom d'effet est globalement unique.

Politique v1 :

- préserver la baseline telle quelle ;
- utiliser `(set logical path, effect key)` comme provenance minimale ;
- détecter les collisions introduites par les mods ;
- différer les overrides inter-set jusqu'à test moteur de la résolution des noms.

## 4. Recipes

27 fichiers de recettes Survival sont présents dans le corpus.

Leur structure n'est pas uniforme :

- listes de recipes ;
- mapping de sets (`craftbot/craftbot.json`) ;
- mappings UUID→résultat (`multitool.json`, `refinery.json`).

`craftbot/craftbot.json` référence actuellement 14 sets.

Le chargement vanilla ouvre ce mapping, ajoute quelques stations fixes puis appelle `LoadCraftingRecipes`.

### Dialecte de fichier

Les fichiers `.json` de Scrap Mechanic peuvent contenir des commentaires `//` inline ou en tête.

Conséquence : **ne pas utiliser un parseur JSON strict comme unique mécanisme**.

Le Composer doit soit :

1. utiliser un parseur compatible JSON5/dialecte Axolot ;
2. ou implémenter un parseur préservant correctement commentaires et structure ;
3. puis produire un format dont l'acceptation par le moteur est testée.

### Politique de merge candidate

Pour les listes de recettes : identité principale = `itemId`, avec règles supplémentaires lorsque plusieurs recettes du même item sont légitimement souhaitées à l'avenir.

Pour le mapping `craftbot.json` : identité = nom du recipe set.

Un mod SMML devrait de préférence fournir son propre fichier de recipes namespacé plutôt que modifier une liste vanilla existante.

## 5. Localisation

`inventoryDescriptions.json` existe pour 11 langues dans la baseline analysée :

```text
Brazilian
Chinese
English
French
German
Italian
Japanese
Korean
Polish
Russian
Spanish
```

Chaque fichier contient actuellement 1 022 clés UUID.

Politique candidate :

- identité = UUID ;
- contribution par langue ;
- valeur identique → déduplication ;
- valeur différente → conflit sauf override explicite ;
- fallback documenté si une langue de mod manque.

## 6. IconMapSurvival.xml

Le fichier observé contient :

- 1 121 éléments `Index` ;
- 1 121 éléments `Frame`.

Le Composer XML doit travailler structurellement, pas par substitution textuelle fragile.

Il doit préserver :

- la syntaxe attendue par MyGUI ;
- les identités/aliases ;
- les coordonnées de frame ;
- la provenance des entrées ajoutées.

## 7. Assets et chemins

Les assets propres à un mod doivent être placés sous un namespace possédé par le mod lorsque Scrap Mechanic accepte cette référence.

Politique cible :

```text
Survival/SMML/Content/<mod-id>/...
```

ou autre racine finale déterminée lors des probes de chargement.

Le Composer doit valider récursivement les références d'un contenu :

```text
Shape
 → renderable
 → mesh/material/textures
 → collider
 → script
```

Un package ne doit pas être considéré valide uniquement parce que son registre racine est syntaxiquement correct.

## 8. Racines logiques détectées

L'analyse statique rencontre :

```text
$GAME_DATA
$SURVIVAL_DATA
$CHALLENGE_DATA
$CONTENT_DATA
$CUSTOMIZATION_DATA
$PARTICLE_EDITOR_DATA
```

Le scanner précédent ne relevait pas encore `$CUSTOMIZATION_DATA` et `$PARTICLE_EDITOR_DATA` dans son extraction profonde.

`$PARTICLE_EDITOR_DATA` correspond à une racine présente dans l'installation capturée.

`$CUSTOMIZATION_DATA` est référencé  notamment par `SurvivalGame.lua`, mais aucune racine équivalente n'est présente dans l'arbre capturé. Il s'agit donc d'une dépendance externe/contextuelle à localiser explicitement avant de considérer la cartographie complète.

## 9. Interface d'adaptateur proposée

Chaque famille du Composer devrait tendre vers :

```text
DiscoverBaseline()
Parse()
EnumerateIdentities()
ValidateContribution()
DetectConflict()
Merge()
Generate()
ValidateGenerated()
EnumerateDependencies()
GetCacheImpact()
ExplainProvenance()
```

Les méthodes peuvent partager une infrastructure commune, mais les règles d'identité et de merge restent propres au domaine.

## 10. Politique initiale par domaine

| Domaine | MVP | Merge initial |
|---|---|---|
| Assets namespacés | oui | ajout, collision chemin interdite |
| Shapes | oui | ajout de set + contrôle UUID |
| Recipes | oui | ajout de recipe set namespacé + contrôle identité |
| Localisation | oui | merge par UUID/langue |
| IconMap | oui | merge XML structurel |
| Scriptable Objects | vague 2 | ajout + UUID |
| Effects | vague 2 | ajout de set ; overrides différés |
| Projectiles | vague 2 | ajout + UUID |
| Harvestables | vague 2 | ajout + UUID |
| Tools | vague 2 | ajout + UUID |
| Characters | vague 3 | différé |
| Kinematics | vague 3 | différé |
| Terrain assets | vague 3 | différé |
| Materials/voxels | vague 3 | différé |
| Tiles/prefabs/blueprints | différé | seulement si besoin concret |

## 11. Critère de sortie GP0.4

Pour les domaines MVP, GP0.4 doit produire :

- le registre racine exact ;
- le format de set ;
- l'identité sémantique ;
- les doublons vanilla connus ;
- la politique de merge ;
- la politique d'override ;
- les dépendances récursives ;
- l'impact cache ;
- un test add/remove ;
- un test conflit ;
- un test moteur lorsque la résolution n'est pas prouvable statiquement.
