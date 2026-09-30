# Cahier des charges v0.1 — Plateforme de modding Scrap Mechanic Survival

**Date de référence :** 28 septembre 2026\
**Statut :** spécification initiale d'architecture et de réalisation\
**Nom de travail :** `SMML` — provisoire

---

# 1. Périmètre et constats issus de l'analyse

## 1.1. Problème à résoudre

L'architecture actuelle modifie directement plusieurs fichiers communs de Survival. Pallet64, le Composteur et la Presse touchent notamment `shapesets.json`, les recettes Craftbot, `RecipeManager.lua`, `IconMapSurvival.xml` et les descriptions d'inventaire. La Presse ajoute en plus une modification de `CarryTool.lua`. Les patchers existants sont prudents et transactionnels, mais la coexistence reste intrinsèquement organisée comme une pile LIFO.

Le handoff identifie déjà comme évolution souhaitable un gestionnaire commun capable de reconstruire une vue finale à partir d'un baseline et de transformations sémantiques, plutôt que de restaurer des copies binaires anciennes.

La plateforme proposée généralise ce principe : **les mods ne modifieront plus eux-mêmes le jeu**.

## 1.2. Contraintes confirmées par le jeu fourni

L'archive fournie contient un corpus Survival très large : environ 570 scripts Lua Survival, plusieurs centaines de classes et callbacks moteur, 82 `.shapeset`, 146 `.effectset`, 24 `.harvestableset`, des bases de Scriptable Objects, Projectiles, recettes, GUI, renderables, prefabs et terrains. Elle contient également les templates de Custom Games et Blocks & Parts fournis par Axolot.

Le code vanilla montre en particulier :

- un chargement massif par `dofile(...)` ;
- des classes Lua structurées autour de callbacks explicites ;
- un grand nombre de globals partagés tels que `g_recipeManager`, `g_unitManager`, `ITEMS`, etc. ;
- des registres déclaratifs séparés du runtime Lua ;
- des transactions de conteneurs et une forte séparation serveur/client ;
- un `CarryTool` dont la création de Shape est effectuée côté serveur ;
- des recettes préchargées depuis un ensemble de fichiers déclaratifs ;
- une architecture de contenu qui ne peut donc pas être remplacée uniquement par un bus d'événements Lua.

La cible actuelle reste le **Survival direct**, pas une Custom Game, afin de préserver les parties Survival existantes et les comportements vanilla.

## 1.3. Architecture retenue

La séparation fonctionnelle cible est :

```text
                         MOD MANAGER
                              │
                           RESOLVER
                              │
                 ┌────────────┴────────────┐
                 │                         │
           HOOK PATCHER             CONTENT COMPOSER
                 │                         │
                 └────────────┬────────────┘
                              │
                       RUNTIME ADAPTER
                              │
                         MODDING API
                              │
                             SDK
                              │
                             MODS
```

Le **Hook Patcher** et le **Content Composer** sont donc deux adaptateurs frères entre Scrap Mechanic et la plateforme.

Le Hook Patcher modifie un nombre réduit de scripts vanilla pour installer des appels directs vers des contrats internes. Il ne contient ni bus général, ni queue, ni logique propre aux mods.

Le Content Composer compose les bases de données et contenus déclaratifs nécessaires au jeu.

L'API transforme ces primitives techniques en contrats stables pour les mods.

Le SDK construit ensuite des abstractions facultatives de plus haut niveau : event bus, queue, scheduler, signaux, machines d'état, helpers réseau, etc.

Le Resolver raisonne sur les packages, versions, dépendances, incompatibilités, capacités et ordre.

Le Mod Manager orchestre l'ensemble sans réimplémenter la logique du Resolver.

---

# 2. Exigences architecturales impératives

## 2.1. Autorité de modification

**AR-001.** Un mod standard ne doit jamais écrire directement dans un fichier vanilla.

**AR-002.** Seuls le Hook Patcher et le Content Composer sont autorisés à produire des modifications du jeu.

**AR-003.** Le Mod Manager ne doit pas modifier lui-même les fichiers de Scrap Mechanic.

**AR-004.** Le Resolver doit pouvoir fonctionner entièrement en lecture seule.

## 2.2. Hooks

**AR-010.** Un hook vanilla doit être minimal.

Exemple conceptuel :

```lua
local r = SMML.Internal.Hooks.carryBeforePlacement(self, params, player)
if r.cancelled then
    return
end
```

**AR-011.** Aucun mod ne doit connaître le fichier vanilla contenant son hook.

**AR-012.** Les paramètres bruts du jeu ne constituent pas le contrat public.

```text
Scrap Mechanic
      │
      ▼
Hook brut
      │
      ▼
Hook Adapter
      │
      ▼
Contexte API stable
      │
      ▼
Mod
```

**AR-013.** Les définitions des hooks doivent être séparées du moteur de patch.

```text
Hook Patcher Engine
+
Hook Definition Pack Scrap Mechanic 1.0.6.889
```

**AR-014.** Une mise à jour du jeu doit idéalement nécessiter un nouveau Hook Definition Pack, et non une modification des mods.

## 2.3. API

**AR-020.** L'API doit être petite et stable.

**AR-021.** Les contrats doivent être versionnables individuellement.

Exemples :

```text
carry.beforePlacement@1
recipe.defaultUnlocks@1
player.inventoryChanged@2
```

**AR-022.** Les contrats doivent spécifier :

- contexte ;
- côté serveur/client ;
- mutabilité ;
- fréquence ;
- politique d'erreur ;
- politique de composition ;
- possibilité d'annulation ;
- valeur de retour ;
- contraintes de performance.

## 2.4. SDK

**AR-030.** Le SDK ne doit pas être nécessaire à l'utilisation directe de l'API.

**AR-031.** Les abstractions telles que bus, queues et schedulers appartiennent au SDK et ne doivent pas être injectées dans les scripts vanilla.

## 2.5. Contenu

**AR-040.** Un mod décrit ses contributions ; il ne décrit pas les mutations textuelles nécessaires pour les installer.

**AR-041.** Toutes les sorties du Composer doivent être déterministes.

**AR-042.** Chaque élément composé doit conserver sa provenance : mod, version et contribution source.

## 2.6. Sécurité et récupération

Les garanties déjà présentes dans les installateurs actuels doivent être conservées ou améliorées : verrou exclusif, SHA-256, écritures atomiques, sauvegarde récursive de `Save/`, rollback, dry-run, refus en cas de modification externe et invalidation ciblée du cache.

**AR-050.** Aucune base de monde ne doit être modifiée directement.

**AR-051.** Aucune purge globale de `Cache/` ne doit être utilisée.

**AR-052.** Un état inconnu ou ambigu doit provoquer un refus d'écriture.

**AR-053.** Un changement de profil susceptible de supprimer du contenu persistant doit provoquer au minimum un snapshot des sauvegardes et un avertissement explicite.

---

# 3. Hors périmètre de la première version

- injection DLL dans l'exécutable ;
- hooking de fonctions C++ ;
- virtual filesystem de type Mod Organizer 2 ;
- téléchargement automatique depuis un dépôt public ;
- marketplace ;
- modifications automatiques des bases `.db` des mondes ;
- prise en charge de tous les systèmes internes de Scrap Mechanic dès la v1 ;
- sandbox de sécurité garantissant qu'un Script Mod malveillant ne puisse rien faire ;
- compatibilité automatique avec des patches externes inconnus ;
- hot reload universel ;
- modification arbitraire de fichiers vanilla demandée directement par un mod.

---

# 4. Découpage général

| Grande phase | Résultat principal                                       |
| ------------ | -------------------------------------------------------- |
| **GP0**      | Compréhension moteur et preuves de faisabilité           |
| **GP1**      | Modèle formel de plateforme et formats                   |
| **GP2**      | Moteur transactionnel, baseline et état                  |
| **GP3**      | Resolver                                                 |
| **GP4**      | Hook Patcher + Hook Packs                                |
| **GP5**      | Content Composer                                         |
| **GP6**      | Runtime Core + Modding API                               |
| **GP7**      | SDK                                                      |
| **GP8**      | Mod Manager, CLI, GUI et diagnostics                     |
| **GP9**      | Migration des trois mods et validation moteur            |
| **GP10**     | Durcissement, documentation et extension de l'écosystème |

---

# GRANDE PHASE 0 — CARTOGRAPHIE MOTEUR ET PREUVES DE FAISABILITÉ

Objectif : **éliminer les hypothèses susceptibles de rendre l'architecture impossible ou inutilement fragile avant d'écrire la plateforme.**

## Phase 0.1 — Baselines du jeu

### Sous-phase 0.1.1 — Corpus de référence

- **0.1.1.1** Enregistrer l'archive 1.0.5 fournie comme fixture structurelle immuable.
- **0.1.1.2** Calculer son inventaire complet par chemin/type/taille/hash.
- **0.1.1.3** Identifier les éléments absents du ZIP mais présents dans son `tree.json`.
- **0.1.1.4** Interdire l'utilisation de cette archive comme baseline binaire de la build 1.0.6.

### Sous-phase 0.1.2 — Baseline 1.0.6

- **0.1.2.1** Capturer les fichiers réellement installés de la build moteur cible.
- **0.1.2.2** Calculer leur fingerprint.
- **0.1.2.3** Comparer les fichiers sensibles avec la fixture 1.0.5.
- **0.1.2.4** Construire une liste des scripts dont les ancres ont changé.
- **0.1.2.5** Stocker la baseline hors de l'arbre actif du jeu.

## Phase 0.2 — Topologie des environnements Lua

### Sous-phase 0.2.1 — Globals et ordre de chargement

- **0.2.1.1** Injecter temporairement un identifiant de runtime dans `SurvivalGame`.
- **0.2.1.2** Vérifier sa visibilité depuis `SurvivalPlayer`.
- **0.2.1.3** Vérifier sa visibilité depuis `CarryTool`.
- **0.2.1.4** Vérifier sa visibilité depuis un `ShapeClass`.
- **0.2.1.5** Vérifier sa visibilité depuis un Scriptable Object.
- **0.2.1.6** Documenter séparément les environnements serveur et client.
- **0.2.1.7** Déterminer quels fichiers peuvent être évalués avant le point d'entrée choisi.

### Sous-phase 0.2.2 — Chargement du runtime

- **0.2.2.1** Créer un loader Lua idempotent minimal.
- **0.2.2.2** Tester plusieurs appels à ce loader.
- **0.2.2.3** Vérifier son comportement avec `server_onRefresh`.
- **0.2.2.4** Vérifier son comportement lors d'un reload de monde.
- **0.2.2.5** Vérifier son comportement après sauvegarde/rechargement.

### Sous-phase 0.2.3 — Isolation d'erreurs

- **0.2.3.1** Exécuter un handler valide via `xpcall`.
- **0.2.3.2** Exécuter un handler provoquant volontairement une erreur.
- **0.2.3.3** Vérifier qu'un second handler continue lorsque cela est sûr.
- **0.2.3.4** Vérifier la qualité du traceback obtenu.
- **0.2.3.5** Définir les situations où une erreur doit au contraire devenir fatale.

## Phase 0.3 — Cartographie des hooks possibles

Le corpus montre plus de 300 implémentations de `server_onCreate`, plus de 260 `client_onCreate`, près de 190 `server_onFixedUpdate`, ainsi qu'un grand nombre de callbacks d'interaction, collisions, projectiles, cellules et mondes. L'objectif ne doit donc pas être de hooker arbitrairement tout le jeu dès le départ.

### Sous-phase 0.3.1 — Inventaire

- **0.3.1.1** Extraire toutes les classes Lua Survival.
- **0.3.1.2** Extraire tous les callbacks moteur.
- **0.3.1.3** Extraire les fonctions globales stratégiques.
- **0.3.1.4** Classer chaque candidat par domaine.
- **0.3.1.5** Classer chaque candidat par fréquence d'appel.

### Sous-phase 0.3.2 — Priorisation

- **0.3.2.1** Identifier les hooks nécessaires à Pallet64.
- **0.3.2.2** Identifier ceux nécessaires au Composteur.
- **0.3.2.3** Identifier ceux nécessaires à la Presse.
- **0.3.2.4** Identifier les hooks génériques qui remplacent plusieurs patches spécifiques.
- **0.3.2.5** Produire la liste minimale de contrats v0.1.

## Phase 0.4 — Cartographie du contenu

### Sous-phase 0.4.1 — Registres actuels

Documenter au minimum :

- Shapes ;
- recipes ;
- icônes ;
- localisation ;
- Scriptable Objects ;
- effets ;
- projectiles ;
- harvestables ;
- outils ;
- personnages ;
- kinematics ;
- terrain/assets ;
- nodes ;
- logs.

### Sous-phase 0.4.2 — Pour chaque registre

Effectuer les étapes unitaires suivantes :

- **0.4.2.1** Identifier le fichier racine.
- **0.4.2.2** Identifier la clé d'identité.
- **0.4.2.3** Identifier le format.
- **0.4.2.4** Identifier la méthode de chargement.
- **0.4.2.5** Identifier le cache concerné.
- **0.4.2.6** Tester l'ajout d'une entrée fictive.
- **0.4.2.7** Tester son retrait.
- **0.4.2.8** Tester un conflit volontaire.
- **0.4.2.9** Documenter la politique de fusion appropriée.

## Phase 0.5 — Réseau et persistance

### Sous-phase 0.5.1 — Transport réseau global

- **0.5.1.1** Évaluer `SurvivalGame.network` comme transport générique.
- **0.5.1.2** Évaluer un Scriptable Object dédié.
- **0.5.1.3** Mesurer les contraintes de callbacks réseau.
- **0.5.1.4** Choisir le transport v1.
- **0.5.1.5** Tester client → serveur.
- **0.5.1.6** Tester serveur → client ciblé.
- **0.5.1.7** Tester broadcast.

### Sous-phase 0.5.2 — Stockage

- **0.5.2.1** Documenter les types de clés réellement acceptés par `sm.storage`.
- **0.5.2.2** Concevoir un namespace de clés par mod.
- **0.5.2.3** Vérifier l'absence de collisions avec les channels vanilla.
- **0.5.2.4** Tester une migration de schéma.
- **0.5.2.5** Tester désactivation/réactivation du mod.

### Gate GP0

Aucun développement structurel de l'API n'est considéré stable tant que :

- l'ordre de chargement n'est pas compris ;
- la visibilité du runtime n'est pas prouvée ;
- le transport réseau n'est pas prototypé ;
- les registres nécessaires au MVP ne sont pas cartographiés ;
- les impacts cache ne sont pas documentés.

---

# GRANDE PHASE 1 — MODÈLE FORMEL DE LA PLATEFORME

## Phase 1.1 — Structure du dépôt

### Sous-phase 1.1.1 — Projets offline

Créer des composants indépendants :

```text
Core
PackageModel
Resolver
HookPatcher
HookPackModel
ContentComposer
GameAdapter.ScrapMechanic
Transactions
Diagnostics
Manager.Cli
Manager.Gui
```

Étapes :

- **1.1.1.1** Créer la solution C# commune.
- **1.1.1.2** Interdire toute dépendance GUI dans les bibliothèques métier.
- **1.1.1.3** Activer tests automatisés par composant.
- **1.1.1.4** Ajouter les fixtures Scrap Mechanic.

### Sous-phase 1.1.2 — Runtime

Créer :

```text
Runtime/Core
Runtime/Internal
Runtime/API
Runtime/Generated
SDK
```

- **1.1.2.1** Définir l'arborescence installée sous `Survival/`.
- **1.1.2.2** Garantir qu'elle est entièrement possédée par la plateforme.
- **1.1.2.3** Garantir qu'elle peut être supprimée indépendamment des fichiers vanilla.

## Phase 1.2 — Manifest de mod

### Sous-phase 1.2.1 — Identité

Définir :

```text
schemaVersion
id
name
version
authors
```

Étapes :

- **1.2.1.1** Définir les règles de `modId`.
- **1.2.1.2** Interdire les IDs ambigus/case-insensitive collisions.
- **1.2.1.3** Définir le versioning.
- **1.2.1.4** Définir le hash canonique du package.

### Sous-phase 1.2.2 — Compatibilité

Définir :

```text
game
api
sdk
requires
optional
conflicts
loadBefore
loadAfter
capabilities
```

### Sous-phase 1.2.3 — Entrypoints

Définir :

```text
shared
server
client
```

- **1.2.3.1** Définir la signature d'un entrypoint.
- **1.2.3.2** Définir son comportement en cas de retour `nil`.
- **1.2.3.3** Interdire implicitement le pattern fragile déjà rencontré avec `dofile()` dans le Composteur.
- **1.2.3.4** Valider chaque entrypoint avant packaging.

## Phase 1.3 — Identités de contenu

### Sous-phase 1.3.1 — UUID

- **1.3.1.1** Maintenir les UUID déjà publiés des trois mods.
- **1.3.1.2** Détecter globalement les collisions.
- **1.3.1.3** Fournir au SDK une génération déterministe optionnelle.
- **1.3.1.4** Enregistrer la provenance de chaque UUID.

### Sous-phase 1.3.2 — Chemins

- **1.3.2.1** Définir un namespace physique par mod.
- **1.3.2.2** Interdire les chemins sortant du namespace.
- **1.3.2.3** Bloquer `..`, chemins absolus et traversées ZIP.
- **1.3.2.4** Traiter les collisions de chemins comme erreurs de résolution.

## Phase 1.4 — Modèle des contrats API

Pour chaque contrat :

```text
id
version
side
frequencyClass
context
mutableFields
resultType
compositionPolicy
errorPolicy
requiredGameCapabilities
```

### Sous-phase 1.4.1 — Catégories

Créer cinq catégories :

1. Notification ;
2. Cancellable ;
3. Transform ;
4. Query ;
5. Service.

### Sous-phase 1.4.2 — Composition

- **1.4.2.1** Spécifier la politique de plusieurs résultats.
- **1.4.2.2** Spécifier les priorités autorisées.
- **1.4.2.3** Spécifier l'ordre déterministe à priorité égale.
- **1.4.2.4** Interdire une politique implicite « dernier mod gagne ».

## Phase 1.5 — Content Intermediate Representation

### Sous-phase 1.5.1 — Contribution

Chaque contribution doit porter :

```text
type
identity
sourceMod
sourceVersion
payload
policy
persistenceImpact
cacheImpact
```

### Sous-phase 1.5.2 — Provenance

- **1.5.2.1** Pouvoir expliquer l'origine de toute entrée générée.
- **1.5.2.2** Pouvoir retrouver tous les fichiers dépendant d'un mod.
- **1.5.2.3** Pouvoir simuler le retrait d'un mod sans écrire.

### Gate GP1

Les schémas `manifest`, `contract`, `hook definition`, `content contribution`, `profile` et `lockfile` doivent être versionnés et validables automatiquement.

---

# GRANDE PHASE 2 — TRANSACTIONS, BASELINES ET ÉTAT DE PLATEFORME

Cette phase généralise les mécanismes déjà éprouvés par les installateurs actuels.

## Phase 2.1 — Détection de l'installation

### Sous-phase 2.1.1 — Localisation

- **2.1.1.1** Supporter un chemin fourni explicitement.
- **2.1.1.2** Ajouter détection Windows.
- **2.1.1.3** Ajouter détection Steam/Proton.
- **2.1.1.4** Détecter le dossier Save séparément.

### Sous-phase 2.1.2 — Fingerprint

- **2.1.2.1** Lire la version observée.
- **2.1.2.2** Hasher les fichiers structurants.
- **2.1.2.3** Identifier un Hook Pack compatible.
- **2.1.2.4** Refuser toute mutation en cas de build inconnue.

## Phase 2.2 — Baseline

### Sous-phase 2.2.1 — Baseline racine

- **2.2.1.1** Capturer l'état pré-plateforme.
- **2.2.1.2** Autoriser cet état à contenir des mods externes déjà présents.
- **2.2.1.3** Le distinguer d'un vanilla Steam connu.
- **2.2.1.4** Conserver les hashes.

### Sous-phase 2.2.2 — Drift

- **2.2.2.1** Vérifier les fichiers suivis avant chaque application.
- **2.2.2.2** Détecter une vérification Steam.
- **2.2.2.3** Détecter un mod externe intervenu après SMML.
- **2.2.2.4** Passer l'état en `needs-rebase`.
- **2.2.2.5** Ne rien écraser automatiquement.

## Phase 2.3 — Transactions

### Sous-phase 2.3.1 — Plan

- **2.3.1.1** Calculer tous les ajouts.
- **2.3.1.2** Calculer toutes les modifications.
- **2.3.1.3** Calculer toutes les suppressions.
- **2.3.1.4** Calculer les caches affectés.
- **2.3.1.5** Afficher le plan en dry-run.

### Sous-phase 2.3.2 — Staging

- **2.3.2.1** Construire la totalité de la sortie hors de l'arbre actif.
- **2.3.2.2** Valider JSON/XML/Lua/manifest.
- **2.3.2.3** Recalculer les hashes.
- **2.3.2.4** Ne commencer aucun commit en cas d'erreur.

### Sous-phase 2.3.3 — Commit

- **2.3.3.1** Acquérir le verrou global.
- **2.3.3.2** Vérifier que Scrap Mechanic est arrêté.
- **2.3.3.3** Snapshotter `Save/`.
- **2.3.3.4** Revalider le fingerprint.
- **2.3.3.5** Écrire par fichier temporaire.
- **2.3.3.6** `fsync`.
- **2.3.3.7** `replace` atomique.
- **2.3.3.8** Quarantainer les caches.
- **2.3.3.9** Vérifier l'état final.

## Phase 2.4 — Recovery

- **2.4.1.1** Détecter une transaction inachevée.
- **2.4.1.2** Vérifier les backups.
- **2.4.1.3** Restaurer uniquement les fichiers suivis.
- **2.4.1.4** Ne jamais restaurer les saves implicitement.
- **2.4.1.5** Produire un rapport de récupération.

### Gate GP2

Une interruption forcée à chaque étape du commit doit pouvoir être récupérée sans perte du baseline ni des sauvegardes.

---

# GRANDE PHASE 3 — RESOLVER

## Phase 3.1 — Découverte des packages

- **3.1.1.1** Scanner les packages installés.
- **3.1.1.2** Valider leur manifest.
- **3.1.1.3** Vérifier leur intégrité.
- **3.1.1.4** Rejeter deux packages portant même ID/version mais bytes différents.

## Phase 3.2 — Graphe de dépendances

### Sous-phase 3.2.1 — Contraintes

- **3.2.1.1** Résoudre dépendances obligatoires.
- **3.2.1.2** Résoudre dépendances facultatives.
- **3.2.1.3** Détecter dépendances absentes.
- **3.2.1.4** Détecter cycles.
- **3.2.1.5** Détecter incompatibilités explicites.

### Sous-phase 3.2.2 — Capacités

Un mod doit pouvoir demander :

```text
carry.beforePlacement >= 1
content.shapes >= 1
api.storage >= 1
```

Étapes :

- **3.2.2.1** Inventorier les capacités fournies par le Hook Pack.
- **3.2.2.2** Inventorier celles du Composer.
- **3.2.2.3** Inventorier celles de l'API.
- **3.2.2.4** Refuser un mod nécessitant une capacité absente.

## Phase 3.3 — Ordre

- **3.3.1.1** Construire le DAG.
- **3.3.1.2** Appliquer `loadBefore/loadAfter`.
- **3.3.1.3** Effectuer le tri topologique.
- **3.3.1.4** Définir un ordre canonique quand plusieurs résultats sont équivalents.
- **3.3.1.5** Garantir la reproductibilité sur deux machines.

## Phase 3.4 — Conflits de contenu

### Sous-phase 3.4.1 — Dédoublonnage

- **3.4.1.1** Identité identique + contenu identique → dédupliquer.
- **3.4.1.2** Conserver les deux provenances.

### Sous-phase 3.4.2 — Conflit

- **3.4.2.1** Identité identique + valeurs différentes → conflit.
- **3.4.2.2** Vérifier si une relation d'override autorisée existe.
- **3.4.2.3** Sinon refuser la résolution.
- **3.4.2.4** Produire un diagnostic précis, champ par champ lorsque possible.

## Phase 3.5 — Lockfile

Le lockfile doit contenir au minimum :

- build Scrap Mechanic ;
- version plateforme ;
- Hook Pack ;
- API ;
- SDK ;
- mods exacts ;
- hashes ;
- ordre ;
- capacités ;
- fingerprint de contenu final.

### Gate GP3

Le même profil et les mêmes packages doivent toujours produire exactement le même graphe et le même lockfile.

---

# GRANDE PHASE 4 — HOOK PATCHER ET HOOK DEFINITION PACKS

## Phase 4.1 — Moteur de patch

### Sous-phase 4.1.1 — Cibles

- **4.1.1.1** Identifier un fichier par chemin.
- **4.1.1.2** Vérifier un ou plusieurs fingerprints supportés.
- **4.1.1.3** Parser/tokeniser le Lua lorsque nécessaire.
- **4.1.1.4** Localiser une ancre structurée.
- **4.1.1.5** Refuser zéro ou plusieurs correspondances non prévues.

### Sous-phase 4.1.2 — Transformations

Supporter au minimum :

```text
insert before
insert after
replace bounded region
wrap function prefix
wrap function postfix
conditional short-circuit
```

### Sous-phase 4.1.3 — Idempotence

- **4.1.3.1** Reconnaître un hook déjà appliqué.
- **4.1.3.2** Vérifier qu'il correspond à la version attendue.
- **4.1.3.3** Ne jamais dupliquer une injection.
- **4.1.3.4** Régénérer depuis le baseline lorsqu'une configuration change.

## Phase 4.2 — Hook Pack

### Sous-phase 4.2.1 — Format

Chaque définition doit inclure :

```text
hookId
contractVersion
gameBuild
targetFile
expectedContext
transformation
adapter
cacheImpact
tests
```

### Sous-phase 4.2.2 — Validation d'un Hook Pack

- **4.2.2.1** Tester sur fixture exacte.
- **4.2.2.2** Tester un fichier volontairement altéré.
- **4.2.2.3** Vérifier le refus sécurisé.
- **4.2.2.4** Vérifier la restauration byte-equivalent.

## Phase 4.3 — Loader runtime minimal

Le « bootstrap » n'est ici qu'une primitive interne.

### Sous-phase 4.3.1 — Boot

- **4.3.1.1** Choisir le ou les points d'entrée prouvés en GP0.
- **4.3.1.2** Ajouter le chargement idempotent de Runtime Core.
- **4.3.1.3** Vérifier serveur.
- **4.3.1.4** Vérifier client.
- **4.3.1.5** Vérifier écouteur/host.

## Phase 4.4 — Premier ensemble de hooks

Le premier Hook Pack doit viser **les besoins concrets des mods existants**, et non l'exhaustivité.

Candidats initiaux à confirmer après GP0 :

- cycle de vie SurvivalGame ;
- cycle de vie Player ;
- extensions de recettes/unlocks ;
- CarryTool : détection de cible d'insertion ;
- CarryTool : placement/drop côté serveur ;
- changements d'inventaire utiles ;
- hooks diagnostics.

### Gate GP4

Le Hook Patcher doit pouvoir être installé puis retiré sans Pallet64, Presse ou Composteur présents, et restituer exactement le baseline suivi.

---

# GRANDE PHASE 5 — CONTENT COMPOSER

## Phase 5.1 — Framework d'adaptateurs

Chaque adaptateur de contenu fournit :

```text
DiscoverBaseline()
ValidateContribution()
GetIdentity()
Merge()
DetectConflict()
Generate()
GetCacheImpact()
ExplainProvenance()
```

## Phase 5.2 — Vague 1 : contenu nécessaire aux trois mods

### Sous-phase 5.2.1 — Assets

- **5.2.1.1** Copier les assets sous un chemin namespacé.
- **5.2.1.2** Prévenir les collisions.
- **5.2.1.3** Vérifier toutes les références.
- **5.2.1.4** Refuser les fichiers temporaires et `__pycache__`.

### Sous-phase 5.2.2 — Shapes

- **5.2.2.1** Parser les contributions Shape.
- **5.2.2.2** Vérifier tous les UUID.
- **5.2.2.3** Vérifier les renderables/colliders/scripts référencés.
- **5.2.2.4** Produire la composition finale.
- **5.2.2.5** Mettre à jour le registre Survival de manière centralisée.
- **5.2.2.6** Associer l'impact `survival_shape_physics` lorsque nécessaire.

### Sous-phase 5.2.3 — Crafting

- **5.2.3.1** Déclarer les recettes par station.
- **5.2.3.2** Vérifier les items produits.
- **5.2.3.3** Vérifier les ingrédients.
- **5.2.3.4** Composer les recipe sets.
- **5.2.3.5** Générer les entrées de chargement nécessaires.
- **5.2.3.6** Déléguer les politiques d'unlock nécessitant du Lua au contrat API approprié.

### Sous-phase 5.2.4 — Localisation

- **5.2.4.1** Supporter plusieurs langues.
- **5.2.4.2** Détecter clés dupliquées.
- **5.2.4.3** Autoriser le doublon uniquement si texte identique ou override explicite.
- **5.2.4.4** Définir un fallback.

### Sous-phase 5.2.5 — Icônes

- **5.2.5.1** Parser IconMap.
- **5.2.5.2** Détecter alias en conflit.
- **5.2.5.3** Vérifier la texture.
- **5.2.5.4** Générer la vue résolue.

## Phase 5.3 — Vague 2

Ajouter progressivement :

- Scriptable Objects ;
- Effects ;
- Projectiles ;
- Harvestables ;
- Tools.

Chaque nouveau type doit passer les mêmes tests de découverte, identité, conflit, génération, cache et retrait.

## Phase 5.4 — Vague 3

À traiter uniquement lorsqu'un mod réel les nécessite :

- Characters ;
- Kinematics ;
- terrain assets ;
- worlds ;
- prefabs/tiles ;
- nodes ;
- trade groups ;
- GUI complexes.

## Phase 5.5 — Sorties générées

- **5.5.1.1** Générer dans un répertoire entièrement géré par la plateforme lorsque possible.
- **5.5.1.2** Modifier les registries vanilla uniquement lorsque nécessaire.
- **5.5.1.3** Maintenir une table de provenance.
- **5.5.1.4** Produire un diff lisible.
- **5.5.1.5** Produire le cache impact plan.

### Gate GP5

Un profil contenant simultanément les contributions statiques des trois mods doit pouvoir être activé/désactivé dans n'importe quel ordre sans aucune logique LIFO.

---

# GRANDE PHASE 6 — RUNTIME CORE ET MODDING API

## Phase 6.1 — Registry runtime des mods

### Sous-phase 6.1.1 — Profil résolu

- **6.1.1.1** Générer côté Manager une représentation Lua du profil.
- **6.1.1.2** Charger cette représentation au runtime.
- **6.1.1.3** Vérifier son fingerprint.
- **6.1.1.4** Charger les mods dans l'ordre résolu.

### Sous-phase 6.1.2 — Entrypoint

Format recommandé :

```lua
return function(api, sdk)
    -- initialisation du mod
end
```

- **6.1.2.1** Vérifier le type retourné.
- **6.1.2.2** Appeler via `xpcall`.
- **6.1.2.3** Fournir un contexte propre au mod.
- **6.1.2.4** Interdire l'enregistrement sous l'identité d'un autre mod.

## Phase 6.2 — Dispatcher des contrats

### Sous-phase 6.2.1 — Hot path

- **6.2.1.1** Utiliser une structure légère.
- **6.2.1.2** Ajouter un fast path sans subscriber.
- **6.2.1.3** Benchmark avant/après.
- **6.2.1.4** Ne pas utiliser le bus générique du SDK dans les hooks moteur fréquents.

### Sous-phase 6.2.2 — Erreurs

- **6.2.2.1** Capturer mod + contrat + handler.
- **6.2.2.2** Logger traceback.
- **6.2.2.3** Compter les erreurs répétées.
- **6.2.2.4** Désactiver le handler lorsque la politique le permet.
- **6.2.2.5** Passer en erreur fatale lorsqu'une invariance du jeu est compromise.

## Phase 6.3 — Services fondamentaux

### Sous-phase 6.3.1 — Logging

Fournir :

```text
trace
debug
info
warn
error
```

avec :

```text
modId
side
tick
contract éventuel
```

### Sous-phase 6.3.2 — Storage

- stockage namespacé ;
- version de schéma ;
- helpers de migration ;
- nettoyage explicitement demandé uniquement.

### Sous-phase 6.3.3 — Content

- résolution ID logique → UUID ;
- résolution d'assets ;
- consultation de la provenance ;
- interrogation des capacités.

### Sous-phase 6.3.4 — Configuration

- config globale du mod ;
- config par profil ;
- validation ;
- valeurs par défaut ;
- migration.

## Phase 6.4 — Réseau

### Sous-phase 6.4.1 — RPC

- **6.4.1.1** Registry de messages par mod.
- **6.4.1.2** IDs déterministes.
- **6.4.1.3** Validation de l'émetteur.
- **6.4.1.4** Limitation des messages inconnus.
- **6.4.1.5** Distinction client→serveur et serveur→client.

### Sous-phase 6.4.2 — Fingerprint multijoueur

- **6.4.2.1** Calculer le fingerprint du profil.
- **6.4.2.2** Échanger le fingerprint lors de la connexion si techniquement possible.
- **6.4.2.3** Détecter une incompatibilité.
- **6.4.2.4** Produire un message exploitable.
- **6.4.2.5** Ne pas tenter de télécharger automatiquement les mods en v1.

## Phase 6.5 — API serveur/client

- **6.5.1.1** Marquer chaque service `server`, `client` ou `shared`.
- **6.5.1.2** Refuser un appel serveur côté client.
- **6.5.1.3** Conserver l'autorité serveur imposée par l'architecture actuelle.
- **6.5.1.4** Ajouter des diagnostics détaillés en mode développeur.

### Gate GP6

Un mod de démonstration doit pouvoir :

- être chargé sans modifier vanilla ;
- écouter un contrat ;
- annuler une action autorisée ;
- stocker un état ;
- envoyer un message réseau ;
- provoquer volontairement une exception sans casser un autre mod.

---

# GRANDE PHASE 7 — SDK

## Phase 7.1 — Event Bus

- **7.1.1.1** `subscribe`.
- **7.1.1.2** `unsubscribe`.
- **7.1.1.3** `once`.
- **7.1.1.4** priorité.
- **7.1.1.5** filtres.
- **7.1.1.6** propagation d'erreur compatible API.

Le bus est une abstraction interne aux mods ; aucun code EventBus ne doit être injecté dans le vanilla.

## Phase 7.2 — Queues et Scheduler

### Sous-phase 7.2.1 — Queue

- **7.2.1.1** FIFO.
- **7.2.1.2** Priority Queue.
- **7.2.1.3** limite de travail par tick.
- **7.2.1.4** annulation.

### Sous-phase 7.2.2 — Scheduler

- **7.2.2.1** tâche au prochain tick.
- **7.2.2.2** délai en ticks.
- **7.2.2.3** tâche périodique.
- **7.2.2.4** arrêt automatique lors du unload.

## Phase 7.3 — Primitives applicatives

Ajouter progressivement :

- Signal ;
- Observable ;
- State Machine ;
- Command ;
- Serializer ;
- cache ;
- debounce/throttle ;
- timers.

## Phase 7.4 — Helpers Scrap Mechanic

Créer des wrappers sûrs autour de :

- containers/transactions ;
- effects ;
- ShapeRenderable ;
- interactions ;
- UUID/content IDs ;
- storage ;
- network ;
- physics queries.

## Phase 7.5 — SDK développeur

### Sous-phase 7.5.1 — Typage/IDE

- **7.5.1.1** Stubs Lua annotés.
- **7.5.1.2** Types API.
- **7.5.1.3** Types SDK.
- **7.5.1.4** JSON Schema des manifests.

### Sous-phase 7.5.2 — CLI développeur

Commandes envisagées :

```text
new
validate
test
pack
inspect
explain
```

### Sous-phase 7.5.3 — Harness de test

- mocks d'API ;
- faux contrats ;
- simulation client/server ;
- transactions de conteneurs ;
- tests des migrations de données.

### Gate GP7

Le même mod de démonstration doit pouvoir être réécrit avec le SDK sans dépendre d'une API privée.

---

# GRANDE PHASE 8 — MOD MANAGER

## Phase 8.1 — CLI d'abord

La CLI constitue l'interface de référence testable.

Commandes minimales :

```text
status
scan
mods
profiles
resolve
plan
apply
verify
launch
disable
uninstall-platform
diagnose
recover
```

## Phase 8.2 — Profils

### Sous-phase 8.2.1 — Gestion

- **8.2.1.1** Créer profil.
- **8.2.1.2** Ajouter mod.
- **8.2.1.3** Désactiver mod.
- **8.2.1.4** Résoudre.
- **8.2.1.5** Générer lockfile.
- **8.2.1.6** Appliquer.

### Sous-phase 8.2.2 — Contenu persistant

- **8.2.2.1** Identifier les mods ajoutant du contenu persistant.
- **8.2.2.2** Avertir avant désactivation.
- **8.2.2.3** Snapshotter les saves avant changement.
- **8.2.2.4** Ne jamais supprimer directement les objets de la sauvegarde.

## Phase 8.3 — Launcher et état de session

### Sous-phase 8.3.1 — Marqueurs

Avant lancement :

```text
session-started
```

Après arrêt propre :

```text
session-completed
```

### Sous-phase 8.3.2 — Safe mode

- **8.3.2.1** Détecter session incomplète.
- **8.3.2.2** Identifier les modifications depuis le dernier lancement réussi.
- **8.3.2.3** Proposer le profil précédent.
- **8.3.2.4** Proposer un lancement plateforme seule.
- **8.3.2.5** Conserver les logs pour diagnostic.

## Phase 8.4 — GUI C\#

L'interface graphique ne doit être qu'un client des mêmes bibliothèques que la CLI.

Écrans initiaux :

1. installation Scrap Mechanic ;
2. profils ;
3. liste de mods ;
4. détails d'un mod ;
5. résolution ;
6. conflits ;
7. plan d'application ;
8. lancement ;
9. diagnostics ;
10. backups/recovery.

## Phase 8.5 — Éditeur de contenu simple

À commencer uniquement après stabilisation du Composer.

Fonctions initiales :

```text
Créer un mod
Ajouter une Shape
Associer renderable/collider
Définir une recette
Ajouter une icône
Ajouter une traduction
Associer un script
Valider
Packager
```

Il doit générer un **package de mod**, jamais éditer directement Survival.

### Gate GP8

Toute opération possible depuis la GUI doit également être réalisable par la CLI ou les bibliothèques Core.

---

# GRANDE PHASE 9 — MIGRATION DES MODS EXISTANTS

Cette phase constitue le véritable test d'architecture.

## Phase 9.1 — Pallet64

Candidat idéal pour la première migration.

### Sous-phase 9.1.1 — Contenu

- **9.1.1.1** Convertir shapes/assets en contributions Composer.
- **9.1.1.2** Convertir recipe.
- **9.1.1.3** Convertir icône.
- **9.1.1.4** Convertir EN/FR.
- **9.1.1.5** Supprimer toute mutation directe du package.

### Sous-phase 9.1.2 — Validation

- **9.1.2.1** Comparer sortie ancienne/nouvelle.
- **9.1.2.2** Vérifier UUID historique.
- **9.1.2.3** Installer/désinstaller.
- **9.1.2.4** Test moteur.

## Phase 9.2 — Composteur

### Sous-phase 9.2.1 — Contenu

Migrer :

- Shape ;
- renderables ;
- collision ;
- textures ;
- recipe ;
- icons ;
- langues.

### Sous-phase 9.2.2 — Runtime

- **9.2.2.1** Adapter le script du Composteur au contexte API.
- **9.2.2.2** Conserver les transactions serveur.
- **9.2.2.3** Conserver le storage existant.
- **9.2.2.4** Conserver les UUID.
- **9.2.2.5** Vérifier les saves existantes.

## Phase 9.3 — Presse

C'est le test le plus important.

### Sous-phase 9.3.1 — Contenu

Migrer les 70 variantes sans modifier directement :

- shapesets ;
- recipes ;
- icons ;
- langues ;
- assets ;
- colliders.

### Sous-phase 9.3.2 — CarryTool

- **9.3.2.1** Retirer le patch propre à la Presse.
- **9.3.2.2** Reproduire le comportement via le contrat API officiel.
- **9.3.2.3** Vérifier insertion client.
- **9.3.2.4** Vérifier validation serveur.
- **9.3.2.5** Vérifier portée/distance.
- **9.3.2.6** Vérifier multijoueur.

### Sous-phase 9.3.3 — Persistance

- **9.3.3.1** Poser une presse avec l'ancien système.
- **9.3.3.2** Sauvegarder.
- **9.3.3.3** Installer la plateforme.
- **9.3.3.4** Charger le monde.
- **9.3.3.5** Vérifier état/conteneurs/storage.
- **9.3.3.6** Répéter avec palettes déjà fabriquées.

## Phase 9.4 — Coexistence

Construire tous les ordres d'opérations pertinents :

```text
A
B
C
A+B
A+C
B+C
A+B+C
```

Puis :

- **9.4.1.1** activer ;
- **9.4.1.2** vérifier ;
- **9.4.1.3** retirer le mod du milieu ;
- **9.4.1.4** vérifier les deux autres ;
- **9.4.1.5** le réactiver ;
- **9.4.1.6** comparer le résultat au lockfile initial.

La contrainte LIFO doit avoir totalement disparu.

## Phase 9.5 — Validation moteur

Reprendre les Gates actuels du projet : package, installateur, mocks, cache puis moteur.

Tests moteur obligatoires :

- craft ;
- placement ;
- interaction ;
- inventories ;
- network ;
- collider ;
- rotations ;
- save/reload ;
- Lift ;
- monde existant ;
- client distant lorsque pertinent ;
- désactivation/réactivation contrôlée ;
- performances.

### Gate GP9

Les trois packages historiques doivent pouvoir devenir de vrais packages SMML ne contenant **aucun code de patch du jeu**.

---

# GRANDE PHASE 10 — DURCISSEMENT ET ÉCOSYSTÈME

## Phase 10.1 — Performance

### Sous-phase 10.1.1 — Runtime sans mod

- **10.1.1.1** Mesurer jeu vanilla.
- **10.1.1.2** Mesurer plateforme installée sans mods.
- **10.1.1.3** Comparer coût CPU/mémoire.
- **10.1.1.4** Optimiser les hot hooks.

### Sous-phase 10.1.2 — Charge

Tester :

- nombreux handlers ;
- nombreuses Shapes moddées ;
- nombreux effets ;
- nombreuses RPC ;
- queues importantes ;
- plusieurs mods simultanés.

## Phase 10.2 — Robustesse

- packages corrompus ;
- ZIP traversal ;
- fichiers manquants ;
- manifest malformé ;
- dépendance cyclique ;
- UUID collision ;
- clé localisation collision ;
- Hook Pack absent ;
- Steam update ;
- cache incohérent ;
- disque plein ;
- interruption de courant simulée ;
- jeu démarré pendant staging ;
- mod externe modifiant un fichier suivi.

## Phase 10.3 — Compatibilité entre builds

### Sous-phase 10.3.1 — Mise à jour Scrap Mechanic

Workflow obligatoire :

```text
nouvelle build
→ fingerprint inconnu
→ blocage des écritures
→ import baseline
→ génération Hook Pack
→ tests statiques
→ tests moteur
→ publication compatibilité
```

Aucune recherche d'ancre « fuzzy » automatique ne doit être considérée sûre en production. L'expérience du projet a déjà montré que les ancres de `CarryTool` changent entre versions.

## Phase 10.4 — Documentation

Produire :

- architecture globale ;
- format package ;
- manifest ;
- guide Content Mod ;
- guide Script Mod ;
- API reference ;
- SDK reference ;
- catalogue des contrats ;
- catalogue des capacités ;
- guide compatibilité ;
- guide migrations ;
- guide tests ;
- guide troubleshooting ;
- guide de création de Hook Packs.

## Phase 10.5 — Mod de référence

Maintenir au moins trois exemples :

1. **Content-only** — Shape + recipe + texte ;
2. **API minimal** — écoute d'un hook ;
3. **SDK avancé** — bus + scheduler + réseau + persistence.

## Phase 10.6 — Extensions différées

Étudier uniquement en présence d'un besoin concret non réalisable autrement :

```text
VFS
DLL loader
hooks natifs C++
signature scanning
accès moteur non exposé
```

---

# 5. Premier périmètre MVP recommandé

Pour éviter de construire immédiatement un équivalent de Forge complet, le premier incrément opérationnel doit s'arrêter à ce qui permet de migrer nos trois mods.

## MVP-A — Infrastructure offline

Inclure :

- baseline ;
- transactions ;
- package manifest ;
- Resolver ;
- Hook Patcher ;
- Hook Pack 1.0.6 cible ;
- Content Composer Shapes/Recipes/Icon/Localization ;
- CLI ;
- lockfile.

## MVP-B — Runtime

Inclure uniquement :

- runtime loader ;
- mod registry ;
- API contracts ;
- logging ;
- config ;
- storage ;
- premier transport réseau ;
- hooks réellement nécessaires aux trois mods.

## MVP-C — Migration

Ordre :

```text
Pallet64
→ Composteur
→ Presse
```

La Presse est volontairement la dernière parce qu'elle teste à la fois contenu complexe, persistance, CarryTool, interactions, réseau et nombreuses variantes de Shapes.

---

# 6. Contrats API à étudier en priorité

Cette liste est un backlog de recherche, pas encore une API figée.

## Cycle de vie

```text
runtime.loaded
game.serverCreated
game.clientCreated
game.fixedUpdate
game.unloading
```

## Player

```text
player.created
player.joined
player.left
player.inventoryChanged
```

## Carry

```text
carry.resolveInsertTarget
carry.beforeSend
carry.beforeDrop
carry.afterDrop
carry.beforePlacement
```

## Recipes

```text
recipes.registering
recipes.defaultUnlocks
```

## Shapes / interactables

```text
shape.created
shape.destroyed
interactable.created
```

Seulement si les tests démontrent qu'un point central fiable existe.

---

# 7. Règles de merge du Content Composer

| Situation                                  | Comportement               |
| ------------------------------------------ | -------------------------- |
| Nouvelle identité                          | ajout                      |
| Même identité + contenu identique          | déduplication              |
| Même identité + contenu différent          | conflit                    |
| Override explicitement déclaré             | application selon Resolver |
| Deux overrides sans ordre déterminé        | conflit                    |
| Asset même chemin + même hash              | déduplication              |
| Asset même chemin + hash différent         | conflit                    |
| UUID identique appartenant à deux contenus | conflit bloquant           |
| Clé traduction identique + texte identique | déduplication              |
| Clé traduction identique + texte différent | conflit/override explicite |

L'ordre de chargement n'est donc jamais utilisé comme substitut silencieux à une politique de compatibilité.

---

# 8. États principaux de la plateforme

```text
uninstalled
installed
profile-resolved
profile-applied
needs-rebase
broken
recovering
safe-mode
```

Une installation ne doit jamais être présentée comme saine lorsque :

- son baseline ne correspond plus ;
- son Hook Pack ne correspond pas ;
- le Content Composer détecte un drift ;
- un package du lockfile manque ;
- un fichier vanilla patché a été modifié extérieurement.

---

# 9. Arborescence d'état indicative

```text
SMML/
├── mods/
│   └── <mod-id>/<version>/
├── profiles/
│   └── <profile-id>/
│       ├── profile.json
│       └── lock.json
├── baselines/
│   └── <game-fingerprint>/
├── hookpacks/
├── backups/
│   └── <transaction-id>/
├── cache/
├── diagnostics/
└── state.json
```

Dans le jeu :

```text
Scrap Mechanic/
└── Survival/
    └── SMML/
        ├── Runtime/
        ├── API/
        ├── SDK/
        ├── Generated/
        └── Content/
```

Les backups ne doivent jamais résider sous cet arbre.

---

# 10. Définition globale de « terminé »

Une étape fonctionnelle n'est considérée terminée que lorsqu'elle possède :

1. comportement spécifié ;
2. implémentation ;
3. test nominal ;
4. test d'erreur ;
5. test de réexécution/idempotence lorsque pertinent ;
6. diagnostic exploitable ;
7. documentation correspondante ;
8. aucune écriture non planifiée ;
9. aucune régression des garanties de sauvegarde ;
10. test moteur lorsque le comportement dépend réellement de Scrap Mechanic.

Le projet a déjà démontré que les mocks et validations de fichiers ne peuvent pas certifier à eux seuls cache, collision, culling, input ou comportement moteur.

---

# 11. Ordre de réalisation recommandé

```text
GP0
  ↓
GP1
  ↓
GP2
  ↓
GP3
  ↓
 ┌─────────────┐
 ↓             ↓
GP4           GP5
 └──────┬──────┘
        ↓
       GP6
        ↓
       GP7
        ↓
       GP8
        ↓
       GP9
        ↓
       GP10
```

`GP4 Hook Patcher` et `GP5 Content Composer` peuvent progresser en parallèle une fois les modèles GP1–GP3 suffisamment stables.

Le premier jalon réellement démonstratif doit être :

```text
profil contenant Pallet64
+
aucun installateur Pallet64
+
aucun patch Pallet64
+
composition et installation uniquement par la plateforme
+
craft / placement / save / reload valides
```

Le second :

```text
Pallet64 + Composteur
+
désactivation de Pallet64 sans toucher au Composteur
+
réactivation produisant exactement le même lockfile et le même contenu généré
```

Le troisième :

```text
Pallet64 + Composteur + Presse
+
CarryTool géré uniquement par un hook plateforme
+
aucun mod ne modifie directement un fichier vanilla
+
UUID et anciennes sauvegardes conservés
+
aucune contrainte LIFO
```
